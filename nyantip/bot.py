import logging
import os
import pprint
import re
import shutil
import sys
import subprocess
import tempfile
import traceback
import time
import zipfile
from datetime import datetime
from decimal import Decimal

import praw
import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined
from sqlalchemy import create_engine
from prawcore.exceptions import PrawcoreException, ResponseException

from . import actions, stats
from .coin import Coin
from .const import __version__
from .user import User
from .util import log_function

logger = logging.getLogger(__package__)
logger.setLevel(logging.DEBUG)
log_decorater = log_function(klass="NyanTip", log_method=logger.info)

EXCEPTION_SLEEP_TIME = 60  # seconds


class NyanTip:
    CONFIG_NAME = "nyantip.yml"
    PERIODIC_TASKS = {
        "expire_pending_tips": {"period": 60},
        "load_banned_users": {"period": 300},
        "update_statistics": {"period": 900},
    }

    def __init__(self):
        self._running = False
        self.banned_users = None
        self.bot = None
        self.commands = []
        self.config = self.parse_config()
        self.database = None
        self.exception_user = None
        self.reddit = None
        self.templates = Environment(
            loader=PackageLoader(__package__),
            trim_blocks=True,
            undefined=StrictUndefined,
        )

        self.coin = Coin(config=self.config["coin"])

    @staticmethod
    def config_path():
        if "APPDATA" in os.environ:  # Windows
            os_config_path = os.environ["APPDATA"]
        elif "XDG_CONFIG_HOME" in os.environ:  # Modern Linux
            os_config_path = os.environ["XDG_CONFIG_HOME"]
        elif "HOME" in os.environ:  # Legacy Linux
            os_config_path = os.path.join(os.environ["HOME"], ".config")
        else:
            raise Exception(
                "APPDATA, XDG_CONFIG_HOME, nor HOME environment variables are set"
            )
        path = os.path.join(os_config_path, NyanTip.CONFIG_NAME)
        if not os.path.isfile(path):
            raise Exception(f"Config file does not exist at {path}")
        return path

    @staticmethod
    def config_to_decimal(container, key):
        assert isinstance(container[key], str)
        container[key] = Decimal(container[key]).normalize()

    @classmethod
    def parse_config(cls):
        path = cls.config_path()
        logger.debug(f"reading config from {path}")
        with open(path) as fp:
            config = yaml.safe_load(fp)
        cls.config_to_decimal(config["coin"], "minimum_tip")
        cls.config_to_decimal(config["coin"], "minimum_withdraw")
        cls.config_to_decimal(config["coin"], "transaction_fee")
        return config

    def _run_loop(self):
        for item in self.reddit.inbox.stream(pause_after=4):
            if item is None:
                now = time.time()
                for task_name, task_metadata in self.PERIODIC_TASKS.items():
                    if now >= task_metadata.setdefault(
                        "next_run_time", now + task_metadata["period"]
                    ):
                        getattr(self, task_name)()
                        now = time.time()
                        task_metadata["next_run_time"] = now + task_metadata["period"]
            else:
                try:
                    self.process_message(item)
                except Exception:
                    item_info = pprint.pformat(vars(item), indent=4)
                    logger.exception(
                        f"Exception processing the following item:\n{item_info}"
                    )

                    if self.exception_user:
                        message = f"Exception\n{traceback.format_exc()}\nItem:\n{item_info}".replace(
                            "\n", "\n\n"
                        )
                        self.exception_user.message(
                            message=message, subject="nyantip exception"
                        )

                    time.sleep(60)  # Let's slow things down if there are issues
                    continue
                item.mark_read()

    def backup(self):
        backup_name = f"backup_nyantip_{datetime.now().strftime('%Y%m%d%H%M')}"
        backup_passphrase = self.config["backup_passphrase"]

        with tempfile.NamedTemporaryFile() as temp_fp:
            with zipfile.ZipFile(temp_fp, mode="w") as zip_fp:
                # Backup config
                zip_fp.write(
                    self.config_path(), arcname=f"{backup_name}/{self.CONFIG_NAME}"
                )

                # Backup database
                database = self.config["database"]["name"]
                with tempfile.NamedTemporaryFile() as database_fp:
                    mysqldump_command = [
                        "mysqldump",
                        "--databases",
                        database,
                        "--host",
                        self.config["database"]["host"],
                        "--port",
                        str(self.config["database"]["port"]),
                        "--single-transaction",
                    ]
                    password = self.config["database"]["password"]
                    if password:
                        mysqldump_command.extend(["--password", password])
                    user = self.config["database"]["user"]
                    if user:
                        mysqldump_command.extend(["--user", user])
                    subprocess.run(mysqldump_command, check=True, stdout=database_fp)
                    zip_fp.write(
                        database_fp.name, arcname=f"{backup_name}/{database}.sql"
                    )

                # Backup wallet
                prefix = self.config["coin"]["name"].lower()
                with tempfile.NamedTemporaryFile() as wallet_fp:
                    self.coin.connection.backupwallet(wallet_fp.name)
                    zip_fp.write(
                        wallet_fp.name, arcname=f"{backup_name}/{prefix}_wallet.dat"
                    )

            if backup_passphrase:
                import gnupg

                gpg = gnupg.GPG()
                temp_fp.seek(0)
                gpg.encrypt_file(
                    temp_fp,
                    output=f"{backup_name}.zip.gpg",
                    passphrase=backup_passphrase,
                    recipients=None,
                    symmetric="AES256",
                )
            else:
                shutil.copy(temp_fp.name, f"{backup_name}.zip")

    def connect_to_database(self):
        info = self.config["database"]
        name = info["name"]
        user = self.config["database"]["user"]
        logger.info(f"Connecting to database {name} as {user or 'anonymous'}")

        credentials = f"{user}:{self.config['database']['password']}@" if user else ""
        self.database = create_engine(
            f"mysql+mysqldb://{credentials}{info['host']}:{info['port']}/{name}?charset=utf8mb4"
        )

    def connect_to_reddit(self):
        self.reddit = praw.Reddit(
            check_for_updates=False,
            ratelimit_seconds=600,
            user_agent=f"nyantip/{__version__} by u/bboe",
            **self.config["reddit"],
        )
        try:
            self.reddit.user.me()  # Ensure credentials are correct
        except ResponseException as exception:
            if exception.response.status_code == 401:
                logger.error("Invalid reddit credentials")
                sys.exit(1)
            raise
        if self.config["exception_user"]:
            self.exception_user = self.reddit.redditor(self.config["exception_user"])

    @log_decorater
    def expire_pending_tips(self):
        pending_hours = int(self.config["pending_hours"])

        for action in actions.actions(
            action="tip",
            created_at=f"created_at < DATE_SUB(NOW(), INTERVAL {pending_hours} HOUR)",
            nyantip=self,
            status="pending",
        ):
            action.expire()

    def load_banned_users(self):
        self.banned_users = set()
        for username in self.config.get("banned", []):
            self.banned_users.add(self.reddit.redditor(username))

        subreddit = self.config["reddit"]["subreddit"]
        for user in self.reddit.subreddit(subreddit).banned(limit=None):
            self.banned_users.add(user)

        logger.info(f"Loaded {len(self.banned_users)} banned user(s)")

    def no_match(self, *, message, message_type):
        logger.info("no match")
        response = self.templates.get_template("didnt-understand.tpl").render(
            config=self.config,
            message=message,
            message_type=message_type,
        )
        User(name=message.author.name, nyantip=self, redditor=message.author).message(
            body=response,
            message=message,
            subject="What?",
        )

    def prepare_commands(self):
        for action, action_config in self.config["commands"].items():
            if isinstance(action_config, str):
                expression = action_config
                command = {
                    "action": action,
                    "only": "message",
                    "regex": re.compile(action_config, re.IGNORECASE | re.DOTALL),
                }
                command["regex"] = re.compile(expression, re.IGNORECASE | re.DOTALL)
                logger.debug(f"ADDED REGEX for {action}: {command['regex'].pattern}")
                self.commands.append(command)
                continue

            for _, option in sorted(action_config.items()):
                expression = (
                    option["regex"]
                    .replace("{REGEX_ADDRESS}", self.coin.config["regex"])
                    .replace("{REGEX_AMOUNT}", r"(\d{1,9}(?:\.\d{0,8})?)")
                    .replace(
                        "{REGEX_KEYWORD}", f"({'|'.join(self.config['keywords'])})"
                    )
                    .replace("{REGEX_USERNAME}", r"/?u/([\w-]{3,20})")
                    .replace("{BOT_NAME}", f"/?u/{self.config['reddit']['username']}")
                )

                command = {
                    "action": action,
                    "address": option["address"],
                    "amount": option["amount"],
                    "destination": option["destination"],
                    "keyword": option["keyword"],
                    "only": option.get("only"),
                }

                command["regex"] = re.compile(expression, re.IGNORECASE | re.MULTILINE)
                logger.debug(f"ADDED REGEX for {action}: {command['regex'].pattern}")
                self.commands.append(command)

    def process_message(self, message):
        message_type = "comment" if message.was_comment else "message"
        if not message.author:
            logger.info(f"ignoring {message_type} with no author")
            return

        if actions.check_action(
            message_id=message.id,
            nyantip=self,
        ):
            logger.warning(
                "duplicate action detected (message.id %s), ignoring",
                message.id,
            )
            return
        if message.author == self.config["reddit"]["username"]:
            logger.debug("ignoring message from self")
            return
        if message.author in self.banned_users:
            logger.info(f"ignoring message from banned user {message.author}")
            return

        for command in self.commands:
            match = command["regex"].search(message.body)
            if match:
                action = command["action"]
                if command["only"] and message_type != command["only"]:
                    logger.debug(
                        f"ignoring {action} because it's only permitted in {command['only']}"
                    )
                    continue
                break
        else:
            logger.debug("no match found")
            self.no_match(message=message, message_type=message_type)
            return

        address = match.group(command["address"]) if command.get("address") else None
        amount = match.group(command["amount"]) if command.get("amount") else None
        destination = (
            match.group(command["destination"]) if command.get("destination") else None
        )
        keyword = match.group(command["keyword"]) if command.get("keyword") else None

        assert not (address and destination)  # Both should never be set
        if not address and not destination:
            if message.was_comment:
                destination = message.parent().author.name
                assert destination

        logger.info(f"{action} from {message.author} ({message_type} {message.id})")
        logger.debug(f"message body:\n<begin>\n{message.body}\n</end>")
        actions.Action(
            action=action,
            amount=amount,
            destination=address or destination,
            keyword=keyword,
            message=message,
            nyantip=self,
        ).perform()

    def run(self):
        self.bot = User(name=self.config["reddit"]["username"], nyantip=self)
        self.prepare_commands()
        self.connect_to_database()
        self.connect_to_reddit()
        self.run_self_check()

        # Run these tasks every start up
        self.load_banned_users()
        self.expire_pending_tips()

        logger.info(f"Bot starting v{__version__}")
        self._running = True
        while self._running:
            try:
                self._run_loop()
            except KeyboardInterrupt:
                self._running = False
            except PrawcoreException:
                logger.exception(
                    f"PrawcoreException in runloop. Sleeping for {EXCEPTION_SLEEP_TIME} seconds."
                )
                time.sleep(EXCEPTION_SLEEP_TIME)
        logger.info(f"Bot stopped gracefully v{__version__}")

    @log_decorater
    def run_self_check(self):
        # Ensure bot is a registered user
        if not self.bot.is_registered():
            self.bot.register()

        # Ensure coin balance is positive
        balance = self.coin.connection.getbalance()
        if balance < 0:
            raise Exception(f"negative wallet balance: {balance}")

        # Ensure pending tips <= bot's escrow balance
        balance = self.bot.balance(kind="tip")
        pending_tips = sum(
            x.amount
            for x in actions.actions(action="tip", nyantip=self, status="pending")
        )
        if balance < pending_tips:
            raise Exception(
                f"Bot's escrow balance ({balance}) < total pending tips ({pending_tips})"
            )

        # Ensure user account balances are not negative
        for row in self.database.execute(
            "SELECT username FROM users ORDER BY username"
        ):
            username = row["username"]
            if User(name=username, nyantip=self).balance(kind="tip") < 0:
                raise Exception(f"{username} has a negative balance")

    def update_statistics(self):
        stats.update_stats(nyantip=self)
        stats.update_tips(nyantip=self)
