"""
    This file is part of ALTcointip.

    ALTcointip is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    ALTcointip is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with ALTcointip.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import os
import sys
import time
from decimal import Decimal

import praw
import prawcore
import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined

from ctb import ctb_action, ctb_coin, ctb_db, ctb_user
from ctb.util import log_function

__version__ = "0.1"

logging.basicConfig(
    datefmt="%H:%M:%S",
    format="%(asctime)s %(levelname)-8s %(name)-12s %(message)s",
)
logging.getLogger("bitcoin").setLevel(logging.DEBUG)
logger = logging.getLogger("ctb")
logger.setLevel(logging.DEBUG)

log_decorater = log_function(klass="CointipBot", log_method=logger.info)


class CointipBot:
    @log_decorater
    def __init__(
        self,
        *,
        init_coin=True,
        init_db=True,
        init_reddit=True,
        self_checks=True,
    ):
        self.banned_users = set()
        self.coin = None
        self.conf = self.parse_config()
        self.runtime = {"regex": []}

        self.bot = ctb_user.CtbUser(
            ctb=self, name=self.conf["reddit"]["auth"]["username"]
        )

        self.jenv = Environment(
            loader=PackageLoader("cointipbot", "tpl/jinja2"),
            trim_blocks=True,
            undefined=StrictUndefined,
        )

        if init_db:
            self.db = self.connect_db()
        if init_coin:
            self.coin = ctb_coin.CtbCoin(conf=self.conf["coin"])
        if init_reddit:
            self.reddit = self.connect_reddit()
            ctb_action.init_regex(self)
            self.load_banned_users()
        if self_checks:
            self.self_checks()

    @staticmethod
    def config_to_decimal(container, key):
        assert isinstance(container[key], str)
        container[key] = Decimal(container[key]).normalize()

    @classmethod
    @log_decorater
    def parse_config(cls):
        conf = {}
        for name in [
            "coin",
            "db",
            "keywords",
            "misc",
            "reddit",
            "regex",
        ]:
            path = os.path.join("conf", f"{name}.yml")
            logger.debug("parse_config(): reading %s", path)
            with open(path) as fp:
                conf[name] = yaml.safe_load(fp)

        cls.config_to_decimal(conf["coin"], "minimum_tip")
        cls.config_to_decimal(conf["coin"], "minimum_withdraw")
        cls.config_to_decimal(conf["coin"], "transaction_fee")

        return conf

    @log_decorater
    def process_message(self, message):
        message_type = "comment" if message.was_comment else "message"
        if not message.author:
            logger.info(f"ignoring {message_type} with no author")
            return

        if ctb_action.check_action(ctb=self, message_id=message.id):
            logger.warning(
                "duplicate action detected (message.id %s), ignoring",
                message.id,
            )
            return
        if message.author == self.conf["reddit"]["auth"]["username"]:
            logger.debug("ignoring message from self")
            return
        if message.author in self.banned_users:
            logger.info(f"ignoring message from banned user {message.author}")
            return

        action_method = (
            ctb_action.eval_comment if message.was_comment else ctb_action.eval_message
        )
        action = action_method(ctb=self, message=message)
        if action:
            logger.info(
                f"{action.action} from {message.author} ({message_type} {message.id})"
            )
            logger.debug(f"message body: {message.body}")
            action.perform()
            return

        logger.info("no match")
        if message_type == "message":
            response = self.jenv.get_template("didnt-understand.tpl").render(
                ctb=self,
                message=message,
                message_type=message_type,
            )
            ctb_user.CtbUser(
                ctb=self, name=message.author, redditor=message.author
            ).tell(
                body=response,
                message=message,
                subject="What?",
            )

    @log_decorater
    def connect_db(self):
        if self.conf["db"]["auth"]["user"]:
            dsn = "mysql+mysqldb://%s:%s@%s:%s/%s?charset=utf8mb4" % (
                self.conf["db"]["auth"]["user"],
                self.conf["db"]["auth"]["password"],
                self.conf["db"]["auth"]["host"],
                self.conf["db"]["auth"]["port"],
                self.conf["db"]["auth"]["dbname"],
            )
        else:
            dsn = f"mysql+mysqldb://{self.conf['db']['auth']['host']}:{self.conf['db']['auth']['port']}/{self.conf['db']['auth']['dbname']}?charset=utf8mb4"

        logger.info(
            "connect_db(): connecting to database %s as %s",
            self.conf["db"]["auth"]["dbname"],
            self.conf["db"]["auth"]["user"] or "anonymous",
        )
        return ctb_db.CointipBotDatabase(dsn).connect()

    @log_decorater
    def connect_reddit(self):
        """
        Returns a praw connection object
        """
        reddit = praw.Reddit(
            check_for_updates=False,
            user_agent=f"nyancointipbot/{__version__} by u/bboe",
            **self.conf["reddit"]["auth"],
        )
        try:
            reddit.user.me()  # Ensure credentials are correct
        except prawcore.exceptions.ResponseException as exception:
            if exception.response.status_code == 401:
                logger.error("connect_reddit(): Invalid auth credentials")
                sys.exit(1)
            raise
        return reddit

    @log_decorater
    def expire_pending_tips(self):
        expire_hours = int(self.conf["misc"]["expire_pending_hours"])

        for action in ctb_action.actions(
            action="tip",
            created_at=f"created_at < DATE_ADD(NOW(), INTERVAL {expire_hours} HOUR)",
            ctb=self,
            status="pending",
        ):
            action.expire()

    @log_decorater
    def load_banned_users(self):
        settings = self.conf["reddit"].get("banned_users")
        if not settings:
            return

        self.banned_users = set()

        subreddit = settings.get("subreddit")
        if subreddit:
            for user in self.reddit.subreddit(subreddit).banned(limit=None):
                self.banned_users.add(user)

        static_list = settings.get("list", [])
        for username in static_list:
            self.banned_users.add(self.reddit.redditor(username))

    def main(self):
        logger.info("main loop starting")
        for item in self.reddit.inbox.stream(pause_after=6):
            if item is None:
                self.expire_pending_tips()
            else:
                self.process_message(item)
                item.mark_read()

    def self_checks(self):
        # Ensure bot is a registered user
        if not self.bot.is_registered():
            self.bot.register()

        # Ensure pending tips <= CointipBot's balance
        balance = self.bot.balance(kind="tip")
        pending_tips = sum(
            x.amount
            for x in ctb_action.actions(action="tip", ctb=self, status="pending")
        )
        if balance < pending_tips:
            raise Exception(
                f"self_checks(): CointipBot's balance ({balance}) < total pending tips ({pending_tips})"
            )

        # Ensure coin balance is positive
        balance = float(self.coin.connection.getbalance())
        if balance < 0:
            raise Exception(f"self_checks(): negative balance: {balance}")

        # Ensure user accounts are intact and balances are not negative
        for row in self.db.execute("SELECT username FROM users ORDER BY username"):
            username = row["username"]
            user = ctb_user.CtbUser(ctb=self, name=username)
            if not user.is_registered():
                raise Exception(f"self_checks(): {username} is not registered")
            if user.balance(kind="tip") < 0:
                raise Exception(f"self_checks(): {username} has a negative balance")
