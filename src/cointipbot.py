#!/usr/bin/env python
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
import smtplib
import sys
import time
import traceback
from email.mime.text import MIMEText
from socket import timeout

import praw
import yaml
from jinja2 import Environment, PackageLoader
from praw.errors import RateLimitExceeded
from requests.exceptions import ConnectionError, HTTPError, Timeout

from ctb import ctb_action, ctb_coin, ctb_db, ctb_exchange, ctb_misc, ctb_user

# Configure CointipBot logger
logging.basicConfig(
    datefmt="%H:%M:%S",
    format="%(asctime)s %(levelname)-8s %(name)-12s %(message)s",
)
logging.getLogger("bitcoin").setLevel(logging.DEBUG)
logger = logging.getLogger("ctb")
logger.setLevel(logging.DEBUG)


class CointipBot(object):
    """
    Main class for cointip bot
    """

    def parse_config(self):
        """
        Returns a Python object with CointipBot configuration
        """
        logger.debug("parse_config(): parsing config files...")

        conf = {}
        try:
            for name in [
                "coins",
                "db",
                "exchanges",
                "fiat",
                "keywords",
                "misc",
                "reddit",
                "regex",
            ]:
                path = os.path.join("conf", f"{name}.yml")
                logger.debug("parse_config(): reading %s", path)
                with open(path) as fp:
                    conf[name] = yaml.safe_load(fp)
        except yaml.YAMLError as e:
            logger.error("parse_config(): error reading config file: %s", e)
            if hasattr(e, "problem_mark"):
                logger.error(
                    "parse_config(): error position: (line %s, column %s)",
                    e.problem_mark.line + 1,
                    e.problem_mark.column + 1,
                )
            sys.exit(1)

        logger.info("parse_config(): config files has been parsed")
        return conf

    def connect_db(self):
        """
        Returns a database connection object
        """
        logger.debug("connect_db(): connecting to database...")

        if self.conf["db"]["auth"]["user"]:
            dsn = "mysql+mysqldb://%s:%s@%s:%s/%s?charset=utf8" % (
                self.conf["db"]["auth"]["user"],
                self.conf["db"]["auth"]["password"],
                self.conf["db"]["auth"]["host"],
                self.conf["db"]["auth"]["port"],
                self.conf["db"]["auth"]["dbname"],
            )
        else:
            dsn = f"mysql+mysqldb://{self.conf['db']['auth']['host']}:{self.conf['db']['auth']['port']}/{self.conf['db']['auth']['dbname']}?charset=utf8"

        dbobj = ctb_db.CointipBotDatabase(dsn)

        try:
            conn = dbobj.connect()
        except Exception as e:
            logger.error("connect_db(): error connecting to database: %s", e)
            sys.exit(1)

        logger.info(
            "connect_db(): connected to database %s as %s",
            self.conf["db"]["auth"]["dbname"],
            self.conf["db"]["auth"]["user"] or "anonymous",
        )
        return conn

    def connect_reddit(self):
        """
        Returns a praw connection object
        """
        logger.debug("connect_reddit(): connecting to Reddit...")

        conn = praw.Reddit(
            user_agent=self.conf["reddit"]["auth"]["user"], check_for_updates=False
        )
        conn.login(
            self.conf["reddit"]["auth"]["user"],
            self.conf["reddit"]["auth"]["password"],
            disable_warning=True,
        )

        logger.info(
            "connect_reddit(): logged in to Reddit as %s",
            self.conf["reddit"]["auth"]["user"],
        )
        return conn

    def self_checks(self):
        """
        Run self-checks before starting the bot
        """

        # Ensure bot is a registered user
        b = ctb_user.CtbUser(name=self.conf["reddit"]["auth"]["user"].lower(), ctb=self)
        if not b.is_registered():
            b.register()

        # Ensure (total pending tips) < (CointipBot's balance)
        for c in self.coins:
            ctb_balance = b.get_balance(coin=c, kind="givetip")
            pending_tips = float(0)
            actions = ctb_action.get_actions(
                atype="givetip", state="pending", coin=c, ctb=self
            )
            for a in actions:
                pending_tips += a.coinval
            if (ctb_balance - pending_tips) < -0.000001:
                raise Exception(
                    "self_checks(): CointipBot's %s balance (%s) < total pending tips (%s)"
                    % (c.upper(), ctb_balance, pending_tips)
                )

        # Ensure coin balances are positive
        for c in self.coins:
            b = float(self.coins[c].conn.getbalance())
            if b < 0:
                raise Exception("self_checks(): negative balance of %s: %s" % (c, b))

        # Ensure user accounts are intact and balances are not negative
        sql = "SELECT username FROM t_users ORDER BY username"
        for mysqlrow in self.db.execute(sql):
            u = ctb_user.CtbUser(name=mysqlrow["username"], ctb=self)
            if not u.is_registered():
                raise Exception(
                    "self_checks(): user %s is_registered() failed"
                    % mysqlrow["username"]
                )
        #    for c in vars(self.coins):
        #        if u.get_balance(coin=c, kind='givetip') < 0:
        #            raise Exception("self_checks(): user %s %s balance is negative" % (mysqlrow['username'], c))

        return True

    def expire_pending_tips(self):
        """
        Decline any pending tips that have reached expiration time limit
        """

        # Calculate timestamp
        seconds = int(self.conf["misc"]["times"]["expire_pending_hours"] * 3600)
        created_before = time.mktime(time.gmtime()) - seconds
        counter = 0

        # Get expired actions and decline them
        for a in ctb_action.get_actions(
            atype="givetip",
            state="pending",
            created_utc="< " + str(created_before),
            ctb=self,
        ):
            a.expire()
            counter += 1

        # Done
        return counter > 0

    def check_inbox(self):
        """
        Evaluate new messages in inbox
        """
        logger.debug("check_inbox()")

        try:

            # Try to fetch some messages
            messages = list(
                ctb_misc.praw_call(
                    self.reddit.get_unread,
                    limit=self.conf["reddit"]["scan"]["batch_limit"],
                )
            )
            messages.reverse()

            # Process messages
            for m in messages:
                # Sometimes messages don't have an author (such as 'you are banned from' message)
                if not m.author:
                    logger.info("check_inbox(): ignoring msg with no author")
                    ctb_misc.praw_call(m.mark_as_read)
                    continue

                logger.info(
                    "check_inbox(): %s from %s",
                    "comment" if m.was_comment else "message",
                    m.author.name,
                )

                # Ignore duplicate messages (sometimes Reddit fails to mark messages as read)
                if ctb_action.check_action(msg_id=m.id, ctb=self):
                    logger.warning(
                        "check_inbox(): duplicate action detected (msg.id %s), ignoring",
                        m.id,
                    )
                    ctb_misc.praw_call(m.mark_as_read)
                    continue

                # Ignore self messages
                if (
                    m.author
                    and m.author.name.lower()
                    == self.conf["reddit"]["auth"]["user"].lower()
                ):
                    logger.debug("check_inbox(): ignoring message from self")
                    ctb_misc.praw_call(m.mark_as_read)
                    continue

                # Ignore messages from banned users
                if m.author and self.conf["reddit"]["banned_users"]:
                    logger.debug(
                        "check_inbox(): checking whether user '%s' is banned..."
                        % m.author
                    )
                    u = ctb_user.CtbUser(
                        name=m.author.name, redditobj=m.author, ctb=self
                    )
                    if u.banned:
                        logger.info(
                            "check_inbox(): ignoring banned user '%s'" % m.author
                        )
                        ctb_misc.praw_call(m.mark_as_read)
                        continue

                action = None
                if m.was_comment:
                    # Attempt to evaluate as comment / mention
                    action = ctb_action.eval_comment(m, self)
                else:
                    # Attempt to evaluate as inbox message
                    action = ctb_action.eval_message(m, self)

                # Perform action, if found
                if action:
                    logger.info(
                        "check_inbox(): %s from %s (m.id %s)",
                        action.type,
                        action.u_from.name,
                        m.id,
                    )
                    logger.debug("check_inbox(): message body: <%s>", m.body)
                    action.do()
                else:
                    logger.info("check_inbox(): no match")
                    if self.conf["reddit"]["messages"]["sorry"] and m.subject not in [
                        "post reply",
                        "comment reply",
                    ]:
                        user = ctb_user.CtbUser(
                            name=m.author.name, redditobj=m.author, ctb=self
                        )
                        tpl = self.jenv.get_template("didnt-understand.tpl")
                        msg = tpl.render(
                            user_from=user.name,
                            what="comment" if m.was_comment else "message",
                            source_link=ctb_misc.permalink(m),
                            ctb=self,
                        )
                        logger.debug("check_inbox(): %s", msg)
                        user.tell(
                            subj="What?",
                            msg=msg,
                            msgobj=m if not m.was_comment else None,
                        )

                # Mark message as read
                ctb_misc.praw_call(m.mark_as_read)

        except (HTTPError, ConnectionError, Timeout, RateLimitExceeded, timeout) as e:
            logger.warning("check_inbox(): Reddit is down (%s), sleeping", e)
            time.sleep(self.conf["misc"]["times"]["sleep_seconds"])
            pass
        except Exception as e:
            logger.exception("check_inbox(): %s", e)
            # raise
        # ^ what do we say to death?
        # 	    logger.error("^not today (^skipped raise)")
        #            raise #not sure if right number of spaces; try to quit on error
        # for now, quitting on error because of dealing with on-going issues; switch
        # back when stable

        logger.debug("check_inbox() DONE")
        return True

    def refresh_ev(self):
        """
        Refresh coin/fiat exchange values using self.exchanges
        """

        # Return if rate has been checked in the past hour
        seconds = int(1 * 3600)
        if hasattr(self.conf["exchanges"], "last_refresh") and self.conf[
            "exchanges"
        ].last_refresh + seconds > int(time.mktime(time.gmtime())):
            logger.debug("refresh_ev(): DONE (skipping)")
            return

        # For each enabled coin...
        for coin, coin_conf in self.conf["coins"].items():
            if coin_conf["enabled"]:

                # Get BTC/coin exchange rate
                values = []
                result = 0.0

                if not coin_conf["unit"] == "btc":
                    # For each exchange that supports this coin...
                    for exchange in self.exchanges:
                        if self.exchanges[exchange].supports_pair(
                            _name1=coin_conf["unit"], _name2="btc"
                        ):
                            # Get ticker value from exchange
                            value = self.exchanges[exchange].get_ticker_value(
                                _name1=coin_conf["unit"], _name2="btc"
                            )
                            if value and float(value) > 0.0:
                                values.append(float(value))

                    # Result is average of all responses
                    if len(values) > 0:
                        result = sum(values) / float(len(values))

                else:
                    # BTC/BTC rate is always 1
                    result = 1.0

                # Assign result to self.runtime['ev']
                if coin not in self.runtime["ev"]:
                    self.runtime["ev"][coin] = {}
                self.runtime["ev"][coin]["btc"] = result

        # For each enabled fiat...
        for fiat, fiat_conf in self.conf["fiat"].items():
            if fiat_conf["enabled"]:

                # Get fiat/BTC exchange rate
                values = []
                result = 0.0

                # For each exchange that supports this fiat...
                for exchange in self.exchanges:
                    if self.exchanges[exchange].supports_pair(
                        _name1="btc", _name2=fiat_conf["unit"]
                    ):
                        # Get ticker value from exchange
                        value = self.exchanges[exchange].get_ticker_value(
                            _name1="btc", _name2=fiat_conf["unit"]
                        )
                        if value and float(value) > 0.0:
                            values.append(float(value))

                # Result is average of all responses
                if len(values) > 0:
                    result = sum(values) / float(len(values))

                # Assign result to self.runtime['ev']
                if "btc" not in self.runtime["ev"]:
                    self.runtime["ev"]["btc"] = {}
                self.runtime["ev"]["btc"][fiat] = result

        logger.debug("refresh_ev(): %s", self.runtime["ev"])

        # Update last_refresh
        self.conf["exchanges"]["last_refresh"] = int(time.mktime(time.gmtime()))

    def coin_value(self, _coin, _fiat):
        """
        Quick method to return _fiat value of _coin
        """
        try:
            value = self.runtime["ev"][_coin]["btc"] * self.runtime["ev"]["btc"][_fiat]
        except KeyError:
            logger.warning("coin_value(%s, %s): KeyError", _coin, _fiat)
            value = 0.0
        return value

    def notify(self, _msg=None):
        """
        Send _msg to configured destination
        """

        # Construct MIME message
        msg = MIMEText(_msg)
        msg["Subject"] = self.conf["misc"]["notify"]["subject"]
        msg["From"] = self.conf["misc"]["notify"]["addr_from"]
        msg["To"] = self.conf["misc"]["notify"]["addr_to"]

        # Send MIME message
        server = smtplib.SMTP(self.conf["misc"]["notify"]["smtp_host"])
        if self.conf["misc"]["notify"]["smtp_tls"]:
            server.starttls()
        server.login(
            self.conf["misc"]["notify"]["smtp_username"],
            self.conf["misc"]["notify"]["smtp_password"],
        )
        server.sendmail(
            self.conf["misc"]["notify"]["addr_from"],
            self.conf["misc"]["notify"]["addr_to"],
            msg.as_string(),
        )
        server.quit()

    def __init__(
        self,
        self_checks=True,
        init_reddit=True,
        init_coins=True,
        init_exchanges=True,
        init_db=True,
    ):
        """
        Constructor. Parses configuration file and initializes bot.
        """
        logger.info("__init__()...")

        self.coins = {}
        self.exchanges = {}
        self.runtime = {"ev": {}, "regex": []}

        # Configuration
        self.conf = self.parse_config()

        # Templating with jinja2
        self.jenv = Environment(
            trim_blocks=True, loader=PackageLoader("cointipbot", "tpl/jinja2")
        )

        # Database
        if init_db:
            self.db = self.connect_db()

        # Coins
        if init_coins and self.conf["coins"]:
            for coin, coin_conf in self.conf["coins"].items():
                if coin_conf["enabled"]:
                    self.coins[coin] = ctb_coin.CtbCoin(_conf=coin_conf)
            if not len(self.coins) > 0:
                logger.error(
                    "__init__(): Error: please enable at least one type of coin"
                )
                sys.exit(1)

        # Exchanges
        if init_exchanges and self.conf["exchanges"]:
            for exchange, exchange_conf in self.conf["exchanges"].items():
                if exchange_conf["enabled"]:
                    self.exchanges[exchange] = ctb_exchange.CtbExchange(
                        _conf=exchange_conf
                    )
            if not len(self.exchanges) > 0:
                logger.warning("__init__(): Warning: no exchanges are enabled")

        # Reddit
        if init_reddit:
            self.reddit = self.connect_reddit()
            # Regex for Reddit messages
            ctb_action.init_regex(self)

        # Self-checks
        if self_checks:
            self.self_checks()

        logger.info(
            "__init__(): DONE, batch-limit = %s, sleep-seconds = %s",
            self.conf["reddit"]["scan"]["batch_limit"],
            self.conf["misc"]["times"]["sleep_seconds"],
        )

    def __str__(self):
        """
        Return string representation of self
        """
        me = "<CointipBot: sleepsec=%s, batchlim=%s, ev=%s"
        me = me % (
            self.conf["misc"]["times"]["sleep_seconds"],
            self.conf["reddit"]["scan"]["batch_limit"],
            self.runtime["ev"],
        )
        return me

    def main(self):
        """
        Main loop
        """

        while True:
            try:
                logger.debug("main(): beginning main() iteration")

                # Refresh exchange rate values
                self.refresh_ev()

                # Expire pending tips first. fuck waiting for this shit.
                self.expire_pending_tips()

                # Check personal messages
                self.check_inbox()

                # Sleep
                logger.debug(
                    "main(): sleeping for %s seconds...",
                    self.conf["misc"]["times"]["sleep_seconds"],
                )
                time.sleep(self.conf["misc"]["times"]["sleep_seconds"])

            except Exception as e:
                logger.error("main(): exception: %s", e)
                tb = traceback.format_exc()
                logger.error("main(): traceback: %s", tb)
                # Send a notification, if enabled
                if self.conf["misc"]["notify"]["enabled"]:
                    self.notify(_msg=tb)
                sys.exit(1)
