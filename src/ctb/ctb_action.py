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
import re

from . import ctb_misc, ctb_stats, ctb_user

logger = logging.getLogger("ctb.action")


class CtbAction(object):
    """
    Action class for cointip bot
    """

    def __init__(
        self,
        *,
        atype,
        coin=None,
        coin_val=None,
        ctb,
        deleted_created_utc=None,
        deleted_msg_id=None,
        from_user=None,
        keyword=None,
        msg,
        subreddit=None,
        to_addr=None,
        to_user=None,
    ):
        """
        Initialize CtbAction object with given parameters and run basic checks
        """
        logger.debug("__init__(type=%s)", atype)

        self.type = atype

        self.coin = coin
        self.coinval = coin_val
        self.keyword = keyword.lower() if keyword else None

        self.msg = msg
        self.ctb = ctb
        self.deleted_msg_id = deleted_msg_id
        self.deleted_created_utc = deleted_created_utc

        self.addr_to = to_addr
        self.u_to = ctb_user.CtbUser(name=to_user, ctb=ctb) if to_user else None
        self.u_from = (
            ctb_user.CtbUser(name=msg.author.name, redditobj=msg.author, ctb=ctb)
            if (msg and msg.author)
            else ctb_user.CtbUser(name=from_user, ctb=ctb)
        )
        self.subreddit = subreddit

        # Do some checks
        if self.type in ["givetip", "withdraw"]:
            if not (bool(self.u_to) ^ bool(self.addr_to)):
                raise Exception(
                    "__init__(atype=%s, from_user=%s): u_to xor addr_to must be set"
                    % (self.type, self.u_from.name)
                )
            if not (bool(self.coin) or bool(self.keyword)):
                raise Exception(
                    "__init__(atype=%s, from_user=%s): coin or keyword must be set"
                    % (self.type, self.u_from.name)
                )
            if not (bool(self.coinval) or bool(self.keyword)):
                raise Exception(
                    "__init__(atype=%s, from_user=%s): coinval or keyword must be set"
                    % (self.type, self.u_from.name)
                )

        # Convert coinval to float, if necesary
        if isinstance(self.coinval, str) and self.coinval.replace(".", "").isnumeric():
            self.coinval = float(self.coinval)

        logger.debug("__init__(): %s", self)

        # Determine coinval if keyword is given instead of numeric value
        if self.type in ["givetip", "withdraw"]:
            if self.keyword and self.coin and not type(self.coinval) in [float, int]:
                # Determine coin value
                logger.debug(
                    "__init__(): determining coin value given '%s'",
                    self.keyword,
                )
                val = self.ctb.conf.keywords[self.keyword].value
                if type(val) == float:
                    self.coinval = val
                elif type(val) == str:
                    logger.debug("__init__(): evaluating '%s'", val)
                    self.coinval = eval(val)
                    if not type(self.coinval) == float:
                        logger.warning(
                            "__init__(atype=%s, from_user=%s): couldn't determine coinval from keyword '%s' (not float)"
                            % (self.type, self.u_from.name, self.keyword)
                        )
                        return None
                else:
                    logger.warning(
                        "__init__(atype=%s, from_user=%s): couldn't determine coinval from keyword '%s' (not float or str)"
                        % (self.type, self.u_from.name, self.keyword)
                    )
                    return None

            # By this point we should have a proper coinval
            if not type(self.coinval) in [float, int]:
                raise Exception(
                    "__init__(atype=%s, from_user=%s): coinval isn't determined"
                    % (self.type, self.u_from.name)
                )

        if self.type in ["givetip"] and not self.coin:
            # Couldn't determine coin, abort
            logger.warning(
                "__init__(): can't determine coin for user %s",
                self.u_from.name,
            )
            return None

        # Verify coinval is set
        if self.type in ["givetip", "withdraw"]:
            assert self.coinval

        logger.debug(
            "__init__(atype=%s, from_user=%s) DONE",
            self.type,
            self.u_from.name,
        )

    def __str__(self):
        """ ""
        Return string representation of self
        """
        me = "<CtbAction: type=%s, msg=%s, from_user=%s, to_user=%s, to_addr=%s, coin=%s, coin_val=%s, subreddit=%s, ctb=%s>"
        me = me % (
            self.type,
            None if self.msg is None else self.msg.body,
            self.u_from,
            self.u_to,
            self.addr_to,
            self.coin,
            self.coinval,
            self.subreddit,
            self.ctb,
        )
        return me

    def save(self, state=None):
        """
        Save action to database
        """
        logger.debug("save(%s)", state)

        # Make sure no negative values exist
        if self.coinval < 0.0:
            self.coinval = 0.0

        realutc = None
        realmsgid = None

        if self.msg:
            realmsgid = self.msg.id
            realutc = self.msg.created_utc
        else:
            realmsgid = self.deleted_msg_id
            realutc = self.deleted_created_utc

        conn = self.ctb.db
        sql = "REPLACE INTO t_action (type, state, created_utc, from_user, to_user, to_addr, coin_val, txid, coin, subreddit, msg_id, msg_link)"
        sql += " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        try:
            mysqlexec = conn.execute(
                sql,
                (
                    self.type,
                    state,
                    realutc,
                    self.u_from.name.lower(),
                    self.u_to.name.lower() if self.u_to else None,
                    self.addr_to,
                    self.coinval,
                    self.txid,
                    self.coin,
                    self.subreddit,
                    realmsgid,
                    ctb_misc.permalink(self.msg),
                ),
            )
            if mysqlexec.rowcount <= 0:
                raise Exception("query didn't affect any rows")
        except Exception as e:
            logger.error(
                "save(%s): error executing query <%s>: %s",
                state,
                sql
                % (
                    self.type,
                    state,
                    self.msg.created_utc if self.msg else None,
                    self.u_from.name.lower(),
                    self.u_to.name.lower() if self.u_to else None,
                    self.addr_to,
                    self.coinval,
                    self.txid,
                    self.coin,
                    self.subreddit,
                    realmsgid,
                    ctb_misc.permalink(self.msg),
                ),
                e,
            )
            raise

        logger.debug("save() DONE")
        return True

    def do(self):
        """
        Call appropriate function depending on action type
        """
        logger.debug("do()")

        if not self.ctb.conf["regex"]["actions"][self.type].enabled:
            msg = self.ctb.jenv.get_template("command-disabled.tpl").render(
                a=self, ctb=self.ctb
            )
            logger.info("do(): action %s is disabled", self.type)
            ctb_misc.praw_call(self.msg.reply, msg)
            return False

        if self.type == "accept":
            if self.accept():
                self.type = "info"
                return self.info()
            else:
                return False

        if self.type == "decline":
            return self.decline()

        if self.type == "givetip":
            result = self.givetip()
            ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_from.name)
            if self.u_to:
                ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_to.name)
            return result

        if self.type == "history":
            return self.history()

        if self.type == "info":
            return self.info()

        if self.type == "register":
            if self.register():
                self.type = "info"
                return self.info()
            else:
                return False

        if self.type == "withdraw":
            return self.givetip()

        logger.debug("do() DONE")
        return None

    def history(self):
        """
        Provide user with transaction history
        """

        # Generate history array
        history = []
        sql_history = self.ctb.conf.db.sql.userhistory.sql
        limit = int(self.ctb.conf.db.sql.userhistory.limit)

        mysqlexec = self.ctb.db.execute(
            sql_history, (self.u_from.name.lower(), self.u_from.name.lower(), limit)
        )
        for m in mysqlexec:
            history_entry = []
            for k in mysqlexec.keys():
                history_entry.append(
                    ctb_stats.format_value(
                        m, k, self.u_from.name.lower(), self.ctb, compact=True
                    )
                )
            history.append(history_entry)

        # Send message to user
        msg = self.ctb.jenv.get_template("history.tpl").render(
            history=history, keys=mysqlexec.keys(), limit=limit, a=self, ctb=self.ctb
        )
        logger.debug("history(): %s", msg)
        ctb_misc.praw_call(self.msg.reply, msg)
        return True

    def accept(self):
        """
        Accept pending tip
        """
        logger.debug("accept()")

        # Register as new user if necessary
        if not self.u_from.is_registered():
            if not self.u_from.register():
                logger.warning("accept(): self.u_from.register() failed")
                self.save("failed")
                return False

        # Get pending actions
        actions = get_actions(
            atype="givetip", to_user=self.u_from.name, state="pending", ctb=self.ctb
        )
        if actions:
            # Accept each action
            for a in actions:
                a.givetip(is_pending=True)
                # Update user stats
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.u_from.name)
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.u_to.name)
        else:
            # No pending actions found, reply with error message
            msg = self.ctb.jenv.get_template("no-pending-tips.tpl").render(
                user_from=self.u_from.name, a=self, ctb=self.ctb
            )
            logger.debug("accept(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)

        # Save action to database
        self.save("completed")

        logger.debug("accept() DONE")
        return True

    def decline(self):
        """
        Decline pending tips
        """
        logger.debug("decline()")

        actions = get_actions(
            atype="givetip", to_user=self.u_from.name, state="pending", ctb=self.ctb
        )
        if actions:
            for a in actions:
                # Move coins back into a.u_from account
                logger.info(
                    "decline(): moving %s %s from %s to %s",
                    a.coinval,
                    a.coin.upper(),
                    self.ctb.conf.reddit.auth.user,
                    a.u_from.name,
                )
                if not self.ctb.coins[a.coin].sendtouser(
                    _userfrom=self.ctb.conf.reddit.auth.user,
                    _userto=a.u_from.name,
                    _amount=a.coinval,
                ):
                    raise Exception("decline(): failed to sendtouser()")

                # Save transaction as declined
                a.save("declined")

                # Update user stats
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.u_from.name)
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.u_to.name)

                # Respond to tip comment
                msg = self.ctb.jenv.get_template("confirmation.tpl").render(
                    title="Declined",
                    a=a,
                    ctb=a.ctb,
                    source_link=ctb_misc.permalink(a.msg),
                )
                logger.debug("decline(): " + msg)
                if self.ctb.conf.reddit.messages.declined:
                    if not ctb_misc.praw_call(a.msg.reply, msg):
                        a.u_from.tell(subj="+tip declined", msg=msg)
                else:
                    a.u_from.tell(subj="+tip declined", msg=msg)

            # Notify self.u_from
            msg = self.ctb.jenv.get_template("pending-tips-declined.tpl").render(
                user_from=self.u_from.name, ctb=self.ctb
            )
            logger.debug("decline(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)

        else:
            msg = self.ctb.jenv.get_template("no-pending-tips.tpl").render(
                user_from=self.u_from.name, ctb=self.ctb
            )
            logger.debug("decline(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)

        # Save action to database
        self.save("completed")

        logger.debug("decline() DONE")
        return True

    def expire(self):
        """
        Expire a pending tip
        """
        logger.debug("expire()")

        # Move coins back into self.u_from account
        logger.info(
            "expire(): moving %s %s from %s to %s",
            self.coinval,
            self.coin.upper(),
            self.ctb.conf.reddit.auth.user,
            self.u_from.name,
        )
        if not self.coin.sendtouser(
            _userfrom=self.ctb.conf.reddit.auth.user,
            _userto=self.u_from.name,
            _amount=self.coinval,
        ):
            raise Exception("expire(): sendtouser() failed")

        # Save transaction as expired
        self.save("expired")

        # Update user stats
        ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_from.name)
        ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_to.name)

        # Respond to tip comment
        msg = self.ctb.jenv.get_template("confirmation.tpl").render(
            title="Expired",
            a=self,
            ctb=self.ctb,
            source_link=ctb_misc.permalink(self.msg),
        )
        logger.debug("expire(): " + msg)
        if self.ctb.conf.reddit.messages.expired:
            if not ctb_misc.praw_call(self.msg.reply, msg):
                self.u_from.tell(subj="+tip expired", msg=msg)
        else:
            self.u_from.tell(subj="+tip expired", msg=msg)

        logger.debug("expire() DONE")
        return True

    def validate(self, is_pending=False):
        """
        Validate an action
        """
        logger.debug("validate()")

        if self.type in ["givetip", "withdraw"]:
            # Check if u_from has registered
            if not self.u_from.is_registered():
                msg = self.ctb.jenv.get_template("not-registered.tpl").render(
                    a=self, ctb=self.ctb
                )
                logger.debug("validate(): %s", msg)
                self.u_from.tell(subj="+tip failed", msg=msg)
                self.save("failed")
                return False

            if self.u_to and not self.u_to.is_on_reddit():
                msg = self.ctb.jenv.get_template("not-on-reddit.tpl").render(
                    a=self, ctb=self.ctb
                )
                logger.debug("validate(): %s", msg)
                self.u_from.tell(subj="+tip failed", msg=msg)
                self.save("failed")
                return False

            # Verify that coin type is set
            if not self.coin:
                msg = self.ctb.jenv.get_template("no-coin-balances.tpl").render(
                    a=self, ctb=self.ctb
                )
                logger.debug("validate(): %s", msg)
                self.u_from.tell(subj="+tip failed", msg=msg)
                self.save("failed")
                return False

            # Verify that u_from has coin address
            if not self.u_from.get_addr(coin=self.coin):
                logger.error(
                    "validate(): user %s doesn't have %s address",
                    self.u_from.name,
                    self.coin.upper(),
                )
                self.save("failed")
                raise Exception

            # Verify minimum transaction size
            txkind = "givetip" if self.u_to else "withdraw"
            if self.coinval < self.coin.txmin[txkind]:
                msg = self.ctb.jenv.get_template("tip-below-minimum.tpl").render(
                    min_value=self.coin.txmin[txkind],
                    a=self,
                    ctb=self.ctb,
                )
                logger.debug("validate(): " + msg)
                self.u_from.tell(subj="+tip failed", msg=msg)
                self.save("failed")
                return False

            # Verify balance (unless it's a pending transaction being processed, in which case coins have been already moved to pending acct)
            if self.u_to and not is_pending:
                # Tip to user (requires less confirmations)
                balance_avail = self.u_from.get_balance(coin=self.coin, kind="givetip")
                if not (
                    balance_avail > self.coinval
                    or abs(balance_avail - self.coinval) < 0.000001
                ):
                    msg = self.ctb.jenv.get_template("tip-low-balance.tpl").render(
                        balance=balance_avail, action_name="tip", a=self, ctb=self.ctb
                    )
                    logger.debug("validate(): " + msg)
                    self.u_from.tell(subj="+tip failed", msg=msg)
                    self.save("failed")
                    return False
            elif self.addr_to:
                # Tip/withdrawal to address (requires more confirmations)
                balance_avail = self.u_from.get_balance(coin=self.coin, kind="withdraw")
                balance_need = self.coinval
                # Add mandatory network transaction fee
                balance_need += self.coin.txfee
                if not (
                    balance_avail > balance_need
                    or abs(balance_avail - balance_need) < 0.000001
                ):
                    msg = self.ctb.jenv.get_template("tip-low-balance.tpl").render(
                        balance=balance_avail,
                        action_name="withdraw",
                        a=self,
                        ctb=self.ctb,
                    )
                    logger.debug("validate(): " + msg)
                    self.u_from.tell(subj="+tip failed", msg=msg)
                    self.save("failed")
                    return False

            # Check if u_to has any pending coin tips from u_from
            if self.u_to and not is_pending:
                if check_action(
                    atype="givetip",
                    state="pending",
                    to_user=self.u_to.name,
                    from_user=self.u_from.name,
                    coin=self.coin,
                    ctb=self.ctb,
                ):
                    # Send notice to u_from
                    msg = self.ctb.jenv.get_template("tip-already-pending.tpl").render(
                        a=self, ctb=self.ctb
                    )
                    logger.debug("validate(): " + msg)
                    self.u_from.tell(subj="+tip failed", msg=msg)
                    self.save("failed")
                    return False

            # Check if u_to has registered, if applicable
            if self.u_to and not self.u_to.is_registered():
                # u_to not registered:
                # - move tip into pending account
                # - save action as 'pending'
                # - notify u_to to accept tip

                # Move coins into pending account
                minconf = self.coin.conf.minconf.givetip
                logger.info(
                    "validate(): moving %s %s from %s to %s (minconf=%s)...",
                    self.coinval,
                    self.coin.upper(),
                    self.u_from.name,
                    self.ctb.conf.reddit.auth.user,
                    minconf,
                )
                if not self.coin.sendtouser(
                    _userfrom=self.u_from.name,
                    _userto=self.ctb.conf.reddit.auth.user,
                    _amount=self.coinval,
                    _minconf=minconf,
                ):
                    raise Exception("validate(): sendtouser() failed")

                # Save action as pending
                self.save("pending")

                # Respond to tip comment
                msg = self.ctb.jenv.get_template("confirmation.tpl").render(
                    title="verified^nyan", a=self, ctb=self.ctb
                )
                logger.debug("validate(): " + msg)
                if self.ctb.conf["reddit"]["messages"]["verified"]:
                    if not ctb_misc.praw_call(self.msg.reply, msg):
                        self.u_from.tell(subj="+tip pending +accept", msg=msg)
                else:
                    self.u_from.tell(subj="+tip pending +accept", msg=msg)

                # Send notice to u_to
                msg = self.ctb.jenv.get_template("tip-incoming.tpl").render(
                    a=self, ctb=self.ctb
                )
                logger.debug("validate(): %s", msg)
                self.u_to.tell(subj="+tip pending", msg=msg)

                # Action saved as 'pending', return false to avoid processing it further
                return False

            # Validate addr_to, if applicable
            if self.addr_to:
                if not self.coin.validateaddr(_addr=self.addr_to):
                    msg = self.ctb.jenv.get_template("address-invalid.tpl").render(
                        a=self, ctb=self.ctb
                    )
                    logger.debug("validate(): " + msg)
                    self.u_from.tell(subj="+tip failed", msg=msg)
                    self.save("failed")
                    return False

        # Action is valid
        logger.debug("validate() DONE")
        return True

    def givetip(self, is_pending=False):
        """
        Initiate tip
        """
        logger.debug("givetip()")

        if self.msg:
            my_id = self.msg.id
        else:
            my_id = self.deleted_msg_id

        # Check if action has been processed
        if check_action(
            atype=self.type, msg_id=my_id, ctb=self.ctb, is_pending=is_pending
        ):
            # Found action in database, returning
            logger.warning(
                "givetipt(): duplicate action %s (msg.id %s), ignoring",
                self.type,
                my_id,
            )
            return False

        # Validate action
        if not self.validate(is_pending=is_pending):
            # Couldn't validate action, returning
            return False

        if self.u_to:
            # Process tip to user

            res = False
            if is_pending:
                # This is accept() of pending transaction, so move coins from pending account to receiver
                logger.info(
                    "givetip(): moving %f from %s to %s...",
                    self.coinval,
                    self.ctb.conf.reddit.auth.user,
                    self.u_to.name,
                )
                res = self.coin.sendtouser(
                    _userfrom=self.ctb.conf.reddit.auth.user,
                    _userto=self.u_to.name,
                    _amount=self.coinval,
                )
            else:
                # This is not accept() of pending transaction, so move coins from tipper to receiver
                logger.info(
                    "givetip(): moving %f from %s to %s...",
                    self.coinval,
                    self.u_from.name,
                    self.u_to.name,
                )
                res = self.coin.sendtouser(
                    _userfrom=self.u_from.name,
                    _userto=self.u_to.name,
                    _amount=self.coinval,
                )

            if not res:
                # Transaction failed
                self.save("failed")

                # Send notice to u_from
                msg = self.ctb.jenv.get_template("tip-went-wrong.tpl").render(
                    a=self, ctb=self.ctb
                )
                self.u_from.tell(subj="+tip failed", msg=msg)

                raise Exception("givetip(): sendtouser() failed")

            # Transaction succeeded
            self.save("completed")

            # Send confirmation to u_to
            msg = self.ctb.jenv.get_template("tip-received.tpl").render(
                a=self, ctb=self.ctb
            )
            logger.debug("givetip(): " + msg)
            self.u_to.tell(subj="+tip received", msg=msg)

            # Send confirmation to u_from
            msg = self.ctb.jenv.get_template("tip-sent.tpl").render(
                a=self, ctb=self.ctb
            )
            logger.debug("givetip(): " + msg)
            self.u_from.tell(subj="+tip sent", msg=msg)

            # This is not accept() of pending transaction, so post verification comment
            if not is_pending:
                msg = self.ctb.jenv.get_template("confirmation.tpl").render(
                    title="verified^nyan", a=self, ctb=self.ctb
                )
                logger.debug("givetip(): " + msg)
                if self.ctb.conf["reddit"]["messages"]["verified"]:
                    if not ctb_misc.praw_call(self.msg.reply, msg):
                        self.u_from.tell(subj="+tip succeeded", msg=msg)
                else:
                    self.u_from.tell(subj="+tip succeeded", msg=msg)

            logger.debug("givetip() DONE")
            return True

        elif self.addr_to:
            # Process tip to address
            try:
                logger.info(
                    "givetip(): sending %f to %s...",
                    self.coinval,
                    self.addr_to,
                )
                self.txid = self.coin.sendtoaddr(
                    _userfrom=self.u_from.name,
                    _addrto=self.addr_to,
                    _amount=self.coinval,
                )

            except Exception:

                # Transaction failed
                self.save("failed")
                logger.error("givetip(): sendtoaddr() failed")

                # Send notice to u_from
                msg = self.ctb.jenv.get_template("tip-went-wrong.tpl").render(
                    a=self, ctb=self.ctb
                )
                self.u_from.tell(subj="+tip failed", msg=msg)

                raise

            # Transaction succeeded
            self.save("completed")

            # Post verification comment
            msg = self.ctb.jenv.get_template("confirmation.tpl").render(
                title="verified^nyan", a=self, ctb=self.ctb
            )
            logger.debug("givetip(): " + msg)
            if self.ctb.conf["reddit"]["messages"]["verified"]:
                if not ctb_misc.praw_call(self.msg.reply, msg):
                    self.u_from.tell(subj="+tip succeeded", msg=msg)
            else:
                self.u_from.tell(subj="+tip succeeded", msg=msg)

            logger.debug("givetip() DONE")
            return True

        logger.debug("givetip() DONE")
        return None

    def info(self):
        """
        Send user info about account
        """
        logger.debug("info()")

        # Check if user exists
        if not self.u_from.is_registered():
            msg = self.ctb.jenv.get_template("not-registered.tpl").render(
                a=self, ctb=self.ctb
            )
            self.u_from.tell(subj="+info failed", msg=msg)
            return False

        # Get coin balances
        try:
            # Get tip balance
            balance = self.coin.getbalance(
                _user=self.u_from.name,
                _minconf=self.coin.conf["minconf"]["givetip"],
            )
        except Exception as exception:
            logger.error(
                "info(%s): error retrieving %s coininfo: %s",
                self.u_from.name,
                self.coin,
                exception,
            )
            raise
        sql = "SELECT address FROM t_addrs WHERE username = '%s' AND coin = '%s'" % (
            self.u_from.name.lower(),
            self.coin.unit,
        )
        mysqlrow = self.ctb.db.execute(sql).fetchone()
        if not mysqlrow:
            raise Exception("info(%s): no result from <%s>" % (self.u_from.name, sql))

        # Format and send message
        msg = self.ctb.jenv.get_template("info.tpl").render(
            action=self,
            address=mysqlrow["address"],
            balance=balance,
            coin=self.coin,
            misc_conf=self.ctb.conf.misc,
        )
        ctb_misc.praw_call(self.msg.reply, msg)

        # Save action to database
        self.save("completed")

        logger.debug("info() DONE")
        return True

    def register(self):
        """
        Register a new user
        """
        logger.debug("register()")

        # If user exists, do nothing
        if self.u_from.is_registered():
            logger.debug(
                "register(%s): user already exists; ignoring request",
                self.u_from.name,
            )
            self.save("failed")
            return True

        result = self.u_from.register()

        # Save action to database
        self.save("completed")

        logger.debug("register() DONE")
        return result


def init_regex(ctb):
    """
    Initialize regular expressions used to match messages and comments
    """
    logger.debug("init_regex()")
    ctb.runtime["regex"] = []

    for action, action_conf in ctb.conf["regex"]["actions"].items():
        if isinstance(action_conf["regex"], str):
            # Add simple message actions (info, register, accept, decline, history)
            entry = {
                "action": action,
                "coin": None,
                "keyword": None,
                "regex": re.compile(action_conf["regex"], re.IGNORECASE | re.DOTALL),
                "rg_address": 0,
                "rg_amount": 0,
                "rg_keyword": 0,
                "rg_to_user": 0,
            }
            logger.debug(
                "ADDED REGEX for %s: %s", entry["action"], entry["regex"].pattern
            )
            ctb.runtime["regex"].append(entry)
        else:
            # Add non-simple actions (givetip, withdraw)
            for _, regex in sorted(action_conf["regex"].items()):
                rval1 = regex["value"]
                rval1 = rval1.replace(
                    "{REGEX_TIP_INIT}", ctb.conf["regex"]["values"]["tip_init"]["regex"]
                )
                rval1 = rval1.replace(
                    "{REGEX_USER}", ctb.conf["regex"]["values"]["username"]["regex"]
                )
                rval1 = rval1.replace(
                    "{REGEX_AMOUNT}", ctb.conf["regex"]["values"]["amount"]["regex"]
                )
                rval1 = rval1.replace(
                    "{REGEX_KEYWORD}", ctb.conf["regex"]["values"]["keywords"]["regex"]
                )

                entry = {
                    "action": action,
                    "coin": None,
                    "rg_address": regex["rg_address"],
                    "rg_amount": regex["rg_amount"],
                    "rg_keyword": regex["rg_keyword"],
                    "rg_to_user": regex["rg_to_user"],
                }

                if regex["rg_coin"] > 0:
                    if not ctb.coin:
                        continue
                    rval2 = rval1.replace(
                        "{REGEX_COIN}", ctb.coin.conf["regex"]["units"]
                    )
                    rval2 = rval2.replace(
                        "{REGEX_ADDRESS}", ctb.coin.conf["regex"]["address"]
                    )
                    regex = re.compile(rval2, re.IGNORECASE | re.DOTALL)
                    entry["coin"] = ctb.coin.conf["unit"]
                else:
                    assert regex["rg_keyword"] > 0
                    regex = re.compile(rval1, re.IGNORECASE | re.DOTALL)
                entry["regex"] = regex
                logger.debug("ADDED REGEX for %s: %s", entry["action"], entry["regex"])
                ctb.runtime["regex"].append(entry)

    logger.info("init_regex() DONE (%s expressions)", len(ctb.runtime["regex"]))
    return None


def eval_message(msg, ctb):
    """
    Evaluate message body and return a CtbAction
    object if successful
    """
    logger.debug("eval_message()")

    body = msg.body
    for regex_info in ctb.runtime["regex"]:

        # Attempt a match
        match = regex_info["regex"].search(body)

        if match:
            # Match found
            logger.debug("eval_message(): match found")

            # Extract matched fields into variables
            to_addr = (
                match.group(regex_info.rg_address)
                if regex_info.rg_address > 0
                else None
            )
            amount = (
                match.group(regex_info.rg_amount) if regex_info.rg_amount > 0 else None
            )
            keyword = (
                match.group(regex_info.rg_keyword)
                if regex_info.rg_keyword > 0
                else None
            )

            if not to_addr and regex_info.action == "givetip":
                logger.debug("eval_message(): can't tip with no to_addr")
                return None

            # Return CtbAction instance with given variables
            return CtbAction(
                atype=regex_info.action,
                msg=msg,
                from_user=msg.author,
                to_user=None,
                to_addr=to_addr,
                coin=regex_info.coin,
                coin_val=amount,
                keyword=keyword,
                ctb=ctb,
            )

    # No match found
    logger.debug("eval_message(): no match found")
    return None


def eval_comment(comment, ctb):
    """
    Evaluate comment body and return a CtbAction object if successful
    """
    logger.debug("eval_comment()")

    body = comment.body
    for r in ctb.runtime["regex"]:

        # Skip non-public actions
        if not ctb.conf["regex"]["actions"][r.action]["public"]:
            continue

        # Attempt a match
        m = r.regex.search(body)

        if m:
            # Match found
            logger.debug("eval_comment(): match found")

            # Extract matched fields into variables
            u_to = m.group(r.rg_to_user)[1:] if r.rg_to_user > 0 else None
            to_addr = m.group(r.rg_address) if r.rg_address > 0 else None
            amount = m.group(r.rg_amount) if r.rg_amount > 0 else None
            keyword = m.group(r.rg_keyword) if r.rg_keyword > 0 else None

            # If no destination mentioned, find parent submission's author
            if not u_to and not to_addr:
                # set u_to to author of parent comment
                u_to = ctb_misc.reddit_get_parent_author(comment, ctb.reddit, ctb)
                if not u_to:
                    # couldn't determine u_to, giving up
                    return None

            # Check if from_user == to_user
            if u_to and comment.author.name.lower() == u_to.lower():
                logger.warning(
                    "eval_comment(): comment.author.name == u_to, ignoring comment",
                    comment.author.name,
                )
                return None

            # Return CtbAction instance with given variables
            logger.debug(
                "eval_comment(): creating action %s: to_user=%s, to_addr=%s, amount=%s, coin=%s"
                % (r.action, u_to, to_addr, amount, r.coin)
            )
            # logger.debug("eval_comment() DONE (yes)")
            return CtbAction(
                atype=r.action,
                msg=comment,
                to_user=u_to,
                to_addr=to_addr,
                coin=r.coin,
                coin_val=amount,
                keyword=keyword,
                subr=comment.subreddit,
                ctb=ctb,
            )

    # No match found
    logger.debug("eval_comment() DONE (no match)")
    return None


def check_action(
    atype=None,
    state=None,
    coin=None,
    msg_id=None,
    created_utc=None,
    from_user=None,
    to_user=None,
    subr=None,
    ctb=None,
    is_pending=False,
):
    """
    Return True if action with given attributes exists in database
    """
    logger.debug("check_action(%s)", atype)

    # Build SQL query
    sql = "SELECT * FROM t_action"
    sql_terms = []
    if (
        atype
        or state
        or coin
        or msg_id
        or created_utc
        or from_user
        or to_user
        or subr
        or is_pending
    ):
        sql += " WHERE "
        if atype:
            sql_terms.append("type = '%s'" % atype)
        if state:
            sql_terms.append("state = '%s'" % state)
        if coin:
            sql_terms.append("coin = '%s'" % coin)
        if msg_id:
            sql_terms.append("msg_id = '%s'" % msg_id)
        if created_utc:
            sql_terms.append("created_utc = %s" % created_utc)
        if from_user:
            sql_terms.append("from_user = '%s'" % from_user.lower())
        if to_user:
            sql_terms.append("to_user = '%s'" % to_user.lower())
        if subr:
            sql_terms.append("subreddit = '%s'" % subr)
        if is_pending:
            sql_terms.append("state <> 'pending'")
        sql += " AND ".join(sql_terms)

    try:
        logger.debug("check_action(): <%s>", sql)
        mysqlexec = ctb.db.execute(sql)
        if mysqlexec.rowcount <= 0:
            logger.debug("check_action() DONE (no)")
            return False
        else:
            logger.debug("check_action() DONE (yes)")
            return True
    except Exception as e:
        logger.error("check_action(): error executing <%s>: %s", sql, e)
        raise

    logger.warning("check_action() DONE (should not get here)")
    return None


def get_actions(
    atype=None,
    state=None,
    deleted_msg_id=None,
    deleted_created_utc=None,
    coin=None,
    msg_id=None,
    created_utc=None,
    from_user=None,
    to_user=None,
    subr=None,
    ctb=None,
):
    """
    Return an array of CtbAction objects from database with given attributes
    """
    logger.debug("get_actions(%s)", atype)

    # Build SQL query
    sql = "SELECT * FROM t_action"
    sql_terms = []
    if atype or state or coin or msg_id or created_utc or from_user or to_user or subr:
        sql += " WHERE "
        if atype:
            sql_terms.append("type = '%s'" % atype)
        if state:
            sql_terms.append("state = '%s'" % state)
        if coin:
            sql_terms.append("coin = '%s'" % coin)
        if msg_id:
            sql_terms.append("msg_id = '%s'" % msg_id)
        if created_utc:
            sql_terms.append("created_utc %s" % created_utc)
        if from_user:
            sql_terms.append("from_user = '%s'" % from_user.lower())
        if to_user:
            sql_terms.append("to_user = '%s'" % to_user.lower())
        if subr:
            sql_terms.append("subreddit = '%s'" % subr)
        sql += " AND ".join(sql_terms)

    while True:
        try:
            r = []
            logger.debug("get_actions(): <%s>", sql)
            mysqlexec = ctb.db.execute(sql)

            if mysqlexec.rowcount <= 0:
                logger.debug("get_actions() DONE (no)")
                return r

            for m in mysqlexec:
                logger.debug("get_actions(): found %s", m["msg_link"])

                # Get PRAW message (msg) and author (msg.author) objects
                try:
                    submission = ctb_misc.praw_call(
                        ctb.reddit.get_submission, m["msg_link"]
                    )
                except Exception:
                    submission = None

                msg = None

                if not submission:
                    logger.warning(
                        "get_actions(): submission not found for %s . msgid %s",
                        m["msg_link"],
                        m["msg_id"],
                    )
                    deleted_msg_id = m["msg_id"]
                    deleted_created_utc = m["created_utc"]
                else:
                    if not len(submission.comments) > 0:
                        logger.warning(
                            "get_actions(): could not fetch msg (deleted?) from msg_link %s",
                            m["msg_link"],
                        )
                        logger.warning(
                            "get_actions(): setting deleted_msg_id %s", m["msg_id"]
                        )
                        deleted_msg_id = m["msg_id"]
                        deleted_created_utc = m["created_utc"]
                    else:
                        msg = submission.comments[0]
                        if not msg.author:
                            logger.warning(
                                "get_actions(): could not fetch msg.author (deleted?) from msg_link %s",
                                m["msg_link"],
                            )
                            logger.warning(
                                "get_actions(): setting msg.author to original tipper %s",
                                m["from_user"],
                            )

                r.append(
                    CtbAction(
                        atype=atype,
                        msg=msg,
                        deleted_msg_id=deleted_msg_id,
                        deleted_created_utc=deleted_created_utc,
                        from_user=m["from_user"],
                        to_user=m["to_user"],
                        to_addr=m["to_addr"] if not m["to_user"] else None,
                        coin=m["coin"],
                        coin_val=float(m["coin_val"]) if m["coin_val"] else None,
                        subr=m["subreddit"],
                        ctb=ctb,
                    )
                )

            logger.debug("get_actions() DONE (yes)")
            return r

        except Exception as e:
            logger.error("get_actions(): error executing <%s>: %s", sql, e)
            raise

    logger.warning("get_actions() DONE (should not get here)")
    return None
