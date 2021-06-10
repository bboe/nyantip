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

from . import ctb_misc

logger = logging.getLogger("ctb.user")


class CtbUser(object):
    """
    User class for cointip bot
    """

    # Basic properties
    name = None
    giftamount = None
    joindate = None
    addr = {}
    banned = False

    # Objects
    prawobj = None
    ctb = None

    def __init__(self, name=None, redditobj=None, ctb=None):
        """
        Initialize CtbUser object with given parameters
        """
        logger.debug("__init__(%s)", name)

        if not bool(name):
            raise Exception("__init__(): name must be set")
        self.name = name

        if not bool(ctb):
            raise Exception("__init__(): ctb must be set")
        self.ctb = ctb

        if bool(redditobj):
            self.prawobj = redditobj

        # Determine if user is banned
        if ctb.conf["reddit"]["banned_users"]:
            if ctb.conf["reddit"]["banned_users"]["method"] == "subreddit":
                for u in ctb.reddit.get_banned(
                    ctb.conf["reddit"]["banned_users"].subreddit
                ):
                    if self.name.lower() == u.name.lower():
                        self.banned = True
            elif ctb.conf["reddit"]["banned_users"]["method"] == "list":
                for username in ctb.conf["reddit"]["banned_users"]["list"]:
                    if self.name.lower() == username.lower():
                        self.banned = True
            else:
                logger.warning(
                    "__init__(): invalid method '%s' in banned_users config"
                    % ctb.conf["reddit"].banned_users.method
                )

        logger.debug("__init__(%s) DONE", name)

    def __str__(self):
        """
        Return string representation of self
        """
        me = "<CtbUser: name=%s, giftamnt=%s, joindate=%s, addr=%s, redditobj=%s, ctb=%s, banned=%s>"
        me = me % (
            self.name,
            self.giftamount,
            self.joindate,
            self.addr,
            self.prawobj,
            self.ctb,
            self.banned,
        )
        return me

    def get_balance(self, *, kind=None):
        logger.debug("balance(%s)", self.name)

        # Ask coin daemon for account balance
        logger.info("balance(%s): getting %s balance", self.name, kind)
        balance = self.ctb.coin.getbalance(
            _user=self.name, _minconf=self.ctb.conf["coin"]["minconf"][kind]
        )
        logger.debug("balance(%s) DONE", self.name)
        return float(balance)

    def get_addr(self, coin=None):
        """
        Return coin address of user
        """
        logger.debug("get_addr(%s, %s)", self.name, coin)

        if hasattr(self.addr, coin):
            return self.addr[coin]

        sql = "SELECT address from t_addrs WHERE username = %s AND coin = %s"
        mysqlrow = self.ctb.db.execute(
            sql, (self.name.lower(), coin.lower())
        ).fetchone()
        if mysqlrow is None:
            logger.debug("get_addr(%s, %s) DONE (no)", self.name, coin)
            return None
        else:
            self.addr[coin] = mysqlrow["address"]
            logger.debug(
                "get_addr(%s, %s) DONE (%s)",
                self.name,
                coin,
                self.addr[coin],
            )
            return self.addr[coin]

        logger.debug("get_addr(%s, %s) DONE (should never happen)", self.name, coin)
        return None

    def is_on_reddit(self):
        """
        Return true if username exists Reddit. Also set prawobj pointer while at it.
        """
        logger.debug("is_on_reddit(%s)", self.name)

        # Return true if prawobj is already set
        if bool(self.prawobj):
            logger.debug("is_on_reddit(%s) DONE (yes)", self.name)
            return True

        try:
            self.prawobj = ctb_misc.praw_call(self.ctb.reddit.get_redditor, self.name)
            if self.prawobj:
                return True
            else:
                return False

        except Exception:
            logger.debug("is_on_reddit(%s) DONE (no)", self.name)
            return False

        logger.warning("is_on_reddit(%s): returning None (shouldn't happen)", self.name)
        return None

    def is_registered(self):
        """
        Return true if user is registered with CointipBot
        """
        logger.debug("is_registered(%s)", self.name)

        try:
            # First, check t_users table
            sql = "SELECT * FROM t_users WHERE username = %s"
            mysqlrow = self.ctb.db.execute(sql, (self.name.lower())).fetchone()

            if mysqlrow is None:
                logger.debug("is_registered(%s) DONE (no)", self.name)
                return False

            else:
                # Next, check t_addrs table for whether  user has correct number of coin addresses
                sql_coins = "SELECT COUNT(*) AS count FROM t_addrs WHERE username = %s"
                mysqlrow_coins = self.ctb.db.execute(
                    sql_coins, (self.name.lower())
                ).fetchone()

                if int(mysqlrow_coins["count"]) != 1:
                    if int(mysqlrow_coins["count"]) == 0:
                        # Bot probably crashed during user registration process
                        # Delete user
                        logger.warning(
                            "is_registered(%s): deleting user, incomplete registration",
                            self.name,
                        )
                        sql_delete = "DELETE FROM t_users WHERE username = %s"
                        self.ctb.db.execute(sql_delete, (self.name.lower()))
                        # User is not registered
                        return False
                    else:
                        raise Exception(
                            "is_registered(%s): user has %s coins but %s active"
                            % (self.name, mysqlrow_coins["count"], 1)
                        )

                # Set some properties
                self.giftamount = mysqlrow["giftamount"]

                # Done
                logger.debug("is_registered(%s) DONE (yes)", self.name)
                return True

        except Exception as e:
            logger.error(
                "is_registered(%s): error while executing <%s>: %s",
                self.name,
                sql % self.name.lower(),
                e,
            )
            raise

        logger.warning(
            "is_registered(%s): returning None (shouldn't happen)", self.name
        )
        return None

    def tell(self, subj=None, msg=None, msgobj=None):
        """
        Send a Reddit message to user
        """
        logger.debug("tell(%s)", self.name)

        if not bool(subj) or not bool(msg):
            raise Exception("tell(%s): subj or msg not set", self.name)

        if not self.is_on_reddit():
            raise Exception("tell(%s): not a Reddit user", self.name)

        if bool(msgobj):
            logger.debug("tell(%s): replying to message", msgobj.id)
            ctb_misc.praw_call(msgobj.reply, msg)
        else:
            logger.debug("tell(%s): sending message", self.name)
            ctb_misc.praw_call(self.prawobj.message, subject=subj, message=msg)

        logger.debug("tell(%s) DONE", self.name)
        return True

    def register(self):
        """
        Add user to database and generate coin addresses
        """
        logger.debug("register(%s)", self.name)

        # Add user to database
        try:
            sql_adduser = "INSERT INTO t_users (username) VALUES (%s)"
            mysqlexec = self.ctb.db.execute(sql_adduser, (self.name.lower()))
            if mysqlexec.rowcount <= 0:
                raise Exception(
                    "register(%s): rowcount <= 0 while executing <%s>"
                    % (self.name, sql_adduser % (self.name.lower()))
                )
        except Exception as e:
            logger.error(
                "register(%s): exception while executing <%s>: %s",
                self.name,
                sql_adduser % (self.name.lower()),
                e,
            )
            raise

        # Get new coin addresses
        address = self.ctb.coin.getnewaddr(_user=self.name.lower())
        logger.info(
            "register(%s): got %s address %s", self.name, self.ctb.coin, address
        )

        # Add coin addresses to database
        try:
            sql = "REPLACE INTO t_addrs (username, coin, address) VALUES (%s, %s, %s)"
            params = (self.name.lower(), self.ctb.coin.conf["unit"], address)
            mysqlexec = self.ctb.db.execute(sql, params)
            if mysqlexec.rowcount <= 0:
                # Undo change to database
                delete_user(_username=self.name.lower(), _db=self.ctb.db)
                raise Exception(
                    "register(%s): rowcount <= 0 while executing <%s>"
                    % (self.name, sql % params)
                )

        except Exception:
            # Undo change to database
            delete_user(_username=self.name.lower(), _db=self.ctb.db)
            raise

        logger.debug("register(%s) DONE", self.name)
        return True


def delete_user(_username=None, _db=None):
    """
    Delete _username from t_users and t_addrs tables
    """
    logger.debug("delete_user(%s)", _username)

    try:
        sql_arr = [
            "DELETE FROM t_users WHERE username = %s",
            "DELETE FROM t_addrs WHERE username = %s",
        ]
        for sql in sql_arr:
            mysqlexec = _db.execute(sql, _username.lower())
            if mysqlexec.rowcount <= 0:
                logger.warning(
                    "delete_user(%s): rowcount <= 0 while executing <%s>",
                    _username,
                    sql % _username.lower(),
                )

    except Exception as e:
        logger.error(
            "delete_user(%s): error while executing <%s>: %s",
            _username,
            sql % _username.lower(),
            e,
        )
        return False

    logger.debug("delete_user(%s) DONE", _username)
    return True
