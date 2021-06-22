import logging
import os
import re
import sys
import time
from decimal import Decimal

import praw
import prawcore
import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined
from sqlalchemy import create_engine

from . import actions, stats
from .coin import Coin
from .const import __version__
from .user import User
from .util import log_function

logger = logging.getLogger(__package__)
logger.setLevel(logging.DEBUG)
log_decorater = log_function(klass="NyanTip", log_method=logger.info)


class NyanTip:
    PERIODIC_TASKS = {
        "expire_pending_tips": {"period": 60},
        "load_banned_users": {"period": 300},
        "update_statistics": {"period": 900},
    }

    def __init__(self):
        self.banned_users = None
        self.bot = None
        self.commands = []
        self.config = self.parse_config()
        self.database = None
        self.reddit = None
        self.templates = Environment(
            loader=PackageLoader(__package__),
            trim_blocks=True,
            undefined=StrictUndefined,
        )

    @staticmethod
    def config_to_decimal(container, key):
        assert isinstance(container[key], str)
        container[key] = Decimal(container[key]).normalize()

    @classmethod
    def parse_config(cls):
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

        path = os.path.join(os_config_path, "nyantip.yml")
        logger.debug(f"reading config from {path}")
        with open(path) as fp:
            config = yaml.safe_load(fp)

        cls.config_to_decimal(config["coin"], "minimum_tip")
        cls.config_to_decimal(config["coin"], "minimum_withdraw")
        cls.config_to_decimal(config["coin"], "transaction_fee")

        return config

    def connect_to_database(self):
        info = self.config["database"]
        name = info["name"]
        username = self.config["database"]["username"]
        logger.info(f"Connecting to database {name} as {username or 'anonymous'}")

        credentials = (
            f"{username}:{self.config['database']['password']}@" if username else ""
        )
        self.database = create_engine(
            f"mysql+mysqldb://{credentials}{info['host']}:{info['port']}/{name}?charset=utf8mb4"
        )

    def connect_to_reddit(self):
        self.reddit = praw.Reddit(
            check_for_updates=False,
            user_agent=f"nyantip/{__version__} by u/bboe",
            **self.config["reddit"],
        )
        try:
            self.reddit.user.me()  # Ensure credentials are correct
        except prawcore.exceptions.ResponseException as exception:
            if exception.response.status_code == 401:
                logger.error("Invalid reddit credentials")
                sys.exit(1)
            raise

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
                    .replace("{REGEX_USERNAME}", r"u/([\w-]{3,20})")
                    .replace("{BOT_NAME}", f"u/{self.config['reddit']['username']}")
                )

                command = {
                    "action": action,
                    "address": option["address"],
                    "amount": option["amount"],
                    "destination": option["destination"],
                    "keyword": option["keyword"],
                    "only": option.get("only"),
                }

                command["regex"] = re.compile(expression, re.IGNORECASE | re.DOTALL)
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
            if command["only"] and message_type != command["only"]:
                continue

            match = command["regex"].search(message.body)
            if match:
                action = command["action"]
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
        logger.debug(f"message body: {message.body}")
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
        self.coin = Coin(config=self.config["coin"])
        self.prepare_commands()
        self.connect_to_database()
        self.connect_to_reddit()
        self.run_self_check()

        # Run these tasks every start up
        self.load_banned_users()
        self.expire_pending_tips()

        logger.info("Bot starting")
        for item in self.reddit.inbox.stream(pause_after=4):
            if item is None:
                now = time.time()
                for task_name, task_metadata in self.PERIODIC_TASKS.items():
                    if now >= task_metadata.get(
                        "next_run_time", now + task_metadata["period"]
                    ):
                        getattr(self, task_name)()
                        now = time.time()
                        task_metadata["next_run_time"] = now + task_metadata["period"]
            else:
                self.process_message(item)
                item.mark_read()

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
            break
            username = row["username"]
            if User(name=username, nyantip=self).balance(kind="tip") < 0:
                raise Exception(f"{username} has a negative balance")

    def update_statistics(self):
        stats.update_stats(nyantip=self)
        stats.update_tips(nyantip=self)
