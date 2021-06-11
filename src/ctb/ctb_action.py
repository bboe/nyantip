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
from decimal import Decimal

from . import ctb_stats, ctb_user
from .util import DummyMessage, log_function

logger = logging.getLogger("ctb.action")


class CtbAction(object):
    @log_function("action", klass="CtbAction")
    def __init__(
        self,
        *,
        action,
        ctb,
        message,
        amount=None,
        destination=None,
        # deleted_created_utc=None,
        # deleted_message_id=None,
        keyword=None,
        # subreddit=None,
    ):

        self.action = action
        self.amount = amount
        self.ctb = ctb
        if action == "tip":
            self.destination = ctb_user.CtbUser(ctb=ctb, name=destination)
        else:
            self.destination = destination
        self.message = message
        self.source = ctb_user.CtbUser(
            ctb=ctb, name=message.author.name, redditor=message.author
        )
        self.transaction_id = None

        # self.deleted_message_id = deleted_message_id
        # self.deleted_created_utc = deleted_created_utc

        # self.subreddit = subreddit

        if self.action in ["tip", "withdraw"]:
            if keyword:
                assert self.amount is None
                value = self.ctb.conf["keywords"][keyword.lower()]["value"]
                if isinstance(value, Decimal):
                    self.amount = value
                else:
                    assert isinstance(value, str)
                    logger.debug(f"__init__(): evaluating {value!r}")
                    self.amount = eval(value)
            else:
                assert isinstance(self.amount, str)
                assert self.amount.replace(".", "").isnumeric()
                self.amount = Decimal(self.amount)

            assert isinstance(self.amount, Decimal)

    def __str__(self):
        return f"<CtbAction: action={self.action}, amount={self.amount} destination={self.destination} source={self.message.author}>"

    @property
    def _amount_formatted(self):
        return self._format_coin(self.amount)

    def _fail(self, subject, template, **template_args):
        response = self.ctb.jenv.get_template(template).render(
            ctb=self.ctb, message=self.message, **template_args
        )
        self.source.tell(body=response, message=self.message, subject=subject)
        self.save(status="failed")
        return False

    def _format_coin(self, quantity):
        return f"{quantity:f} {self.ctb.conf['coin']['name']}"

    def action_accept(self):
        logger.debug("accept()")

        # Register as new user if necessary
        if not self.source.is_registered():
            if not self.source.register():
                logger.warning("accept(): self.source.register() failed")
                self.save(status="failed")
                return False

        # Get pending actions
        actions = get_actions(
            atype="tip", to_user=self.source, state="pending", ctb=self.ctb
        )
        if actions:
            # Accept each action
            for a in actions:

                logger.info(
                    "tip(): moving %f from %s to %s...",
                    self.amount,
                    self.ctb.conf["reddit"]["auth"]["username"],
                    self.u_to,
                )
                res = self.coin.sendtouser(
                    _userfrom=self.ctb.conf["reddit"]["auth"]["username"],
                    _userto=self.u_to,
                    _amount=self.amount,
                )

                # Update user stats
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.source)
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.u_to)
        else:
            # No pending actions found, reply with error message
            message = self.ctb.jenv.get_template("no-pending-tips.tpl").render(
                user_from=self.source, a=self, ctb=self.ctb
            )
            logger.debug("accept(): %s", message)
            ctb_misc.praw_call(self.message.reply, message)

        # Save action to database
        self.save(status="completed")

        logger.debug("accept() DONE")
        return True

    def action_decline(self):
        logger.debug("decline()")

        actions = get_actions(
            atype="tip", to_user=self.source, state="pending", ctb=self.ctb
        )
        if actions:
            for a in actions:
                # Move coins back into a.source account
                logger.info(
                    "decline(): moving %s %s from %s to %s",
                    a.coinval,
                    a.coin.conf["name"].upper(),
                    self.ctb.conf["reddit"]["auth"]["username"],
                    a.source,
                )
                if not self.ctb.coins[a.coin].sendtouser(
                    _userfrom=self.ctb.conf["reddit"]["auth"]["username"],
                    _userto=a.source,
                    _amount=a.coinval,
                ):
                    raise Exception("decline(): failed to sendtouser()")

                # Save transaction as declined
                a.save("declined")

                # Update user stats
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.source)
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.u_to)

                # Respond to tip comment
                message = self.ctb.jenv.get_template("confirmation.tpl").render(
                    action=action.action,
                    ctb=action.ctb,
                    message=action.message,
                    title="Declined",
                )
                logger.debug("decline(): " + message)
                a.source.tell(subject="tip declined", message=message)

            # Notify self.source
            message = self.ctb.jenv.get_template("pending-tips-declined.tpl").render(
                user_from=self.source, ctb=self.ctb
            )
            logger.debug("decline(): %s", message)
            ctb_misc.praw_call(self.message.reply, message)

        else:
            message = self.ctb.jenv.get_template("no-pending-tips.tpl").render(
                user_from=self.source, ctb=self.ctb
            )
            logger.debug("decline(): %s", message)
            ctb_misc.praw_call(self.message.reply, message)

        # Save action to database
        self.save(status="completed")

        logger.debug("decline() DONE")

    def action_history(self):
        history = []

        response = self.ctb.db.execute(
            self.ctb.conf["db"]["sql"]["history"], (self.destination, self.source)
        )
        for row in response:
            history_entry = []
            for key in response.keys():
                history_entry.append(
                    ctb_stats.format_value(
                        row, key, self.source, self.ctb, compact=True
                    )
                )
            history.append(history_entry)

        if history:
            response = self.ctb.jenv.get_template("history.tpl").render(
                ctb=self.ctb,
                history=history,
                keys=response.keys(),
                message=self.message,
            )
        else:
            response = self.ctb.jenv.get_template("history-empty.tpl").render(
                ctb=self.ctb, message=self.message
            )
        logger.debug(f"history(): {response}")
        self.message.reply(response)

    @log_function(klass="CtbAction")
    def action_info(self):
        if not self.source.is_registered():
            response = self.ctb.jenv.get_template("not-registered.tpl").render(
                ctb=self.ctb, message=self.message
            )
            self.source.tell(body=response, message=self.message, subject="info failed")
            return False

        balance = self.ctb.coin.balance(
            minconf=self.ctb.coin.conf["minconf"]["tip"],
            user=self.source.name,
        )
        row = self.ctb.db.execute(
            "SELECT address FROM users WHERE username = %s", self.source
        ).fetchone()

        response = self.ctb.jenv.get_template("info.tpl").render(
            action=self,
            address=row["address"],
            balance=balance,
            coin=self.ctb.coin,
            ctb=self.ctb,
            message=self.message,
            misc_conf=self.ctb.conf["misc"],
        )
        self.message.reply(response)

        # Save action to database
        self.save(status="completed")

        return True

    @log_function(klass="CtbAction")
    def action_register(self):
        if self.source.is_registered():
            logger.debug(
                f"register({self.source}): user already exists; ignoring request"
            )
            self.save(status="failed")
        else:
            self.source.register()
            self.save(status="completed")
        self.action = "info"
        self.action_info()

    @log_function(klass="CtbAction")
    def action_tip(self):
        assert self.destination
        if not self.validate():
            return

        try:
            self.ctb.coin.send(
                amount=self.amount,
                destination=self.destination,
                source=self.source,
            )
        except Exception:
            logger.exception("action_tip(): failed")
            return self._fail(
                "tip failed",
                "tip-went-wrong.tpl",
                action_name=self.action,
                amount_formatted=self._amount_formatted,
                destination=self.destination,
                to_address=False,
            )

        self.save(status="completed")

        response = self.ctb.jenv.get_template("confirmation.tpl").render(
            amount_formatted=self._amount_formatted,
            ctb=self.ctb,
            destination=self.destination,
            message=self.message,
            title="verified^nyan",
            to_address=False,
            transaction_id=None,
        )
        self.source.tell(body=response, message=self.message, subject="tip succeeded")

        dummy_message = DummyMessage(self.destination, self.message.context)
        response = self.ctb.jenv.get_template("tip-received.tpl").render(
            amount_formatted=self._amount_formatted,
            ctb=self.ctb,
            dummy_message=dummy_message,
            source=self.message.author,
        )
        self.destination.tell(body=response, subject="tip received")

    @log_function(klass="CtbAction")
    def action_withdraw(self):
        assert self.destination
        if not self.validate():
            return

        # TODO
        # Use a move if the address belongs to the local wallet

        try:
            self.transaction_id = self.ctb.coin.transfer(
                address=self.destination, amount=self.amount, source=self.source.name
            )
        except Exception:
            logger.exception("action_withdraw(): failed")
            return self._fail(
                "withdraw failed",
                "tip-went-wrong.tpl",
                action_name=self.action,
                amount_formatted=self._amount_formatted,
                destination=self.destination,
                to_address=True,
            )

        self.save(status="completed")
        response = self.ctb.jenv.get_template("confirmation.tpl").render(
            amount_formatted=self._amount_formatted,
            ctb=self.ctb,
            destination=self.destination,
            message=self.message,
            title="verified^nyan",
            to_address=True,
            transaction_id=self.transaction_id,
        )
        self.source.tell(
            body=response, message=self.message, subject="withdraw succeeded"
        )

    def expire(self):
        """
        Expire a pending tip
        """
        logger.debug("expire()")

        # Move coins back into self.source account
        logger.info(
            "expire(): moving %s %s from %s to %s",
            self.amount,
            self.coin.conf["name"].upper(),
            self.ctb.conf["reddit"]["auth"]["username"],
            self.source,
        )
        if not self.coin.sendtouser(
            _userfrom=self.ctb.conf["reddit"]["auth"]["username"],
            _userto=self.source,
            _amount=self.amount,
        ):
            raise Exception("expire(): sendtouser() failed")

        # Save transaction as expired
        self.save(status="expired")

        # Update user stats
        ctb_stats.update_user_stats(ctb=self.ctb, username=self.source)
        ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_to)

        response = self.ctb.jenv.get_template("confirmation.tpl").render(
            action=self,
            ctb=self.ctb,
            message=self.message,
            title="Expired",
        )
        self.source.tell(body=response, message=self.message, subject="tip expired")

    @log_function(klass="CtbAction")
    def perform(self):
        if self.action == "accept":
            if self.action_accept():
                self.action = "info"
                self.action_info()
        elif self.action == "decline":
            self.action_decline()
        elif self.action == "history":
            self.action_history()
        elif self.action == "info":
            self.action_info()
        elif self.action == "register":
            self.action_register()
        elif self.action == "tip":
            self.action_tip()
            # ctb_stats.update_user_stats(ctb=self.ctb, username=self.source)
            # ctb_stats.update_user_stats(ctb=self.ctb, username=self.destination)
        else:
            assert self.action == "withdraw"
            self.action_withdraw()

    @log_function("status", klass="CtbAction")
    def save(self, *, status):
        assert self.amount is None or self.amount > 0

        #     realmessageid = self.deleted_message_id
        #     realutc = self.deleted_created_utc

        result = self.ctb.db.execute(
            "REPLACE INTO actions (action, amount, destination, message_id, source, status, transaction_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                self.action,
                self.amount,
                self.destination,
                self.message.id,
                self.source,
                status,
                self.transaction_id,
            ),
        )
        assert result.rowcount == 1

    @log_function(klass="CtbAction", log_response=True)
    def validate(self):
        subject = f"{self.action} failed"

        # First see if the author is registered
        if not self.source.is_registered():
            return self._fail(subject, "not-registered.tpl")

        # Second ensure the amount is larger than the necessary minimum
        minimum = self.ctb.coin.conf[f"minimum_{self.action}"]
        if self.amount < minimum:
            return self._fail(
                subject,
                "tip-below-minimum.tpl",
                action_name=self.action,
                amount_formatted=self._amount_formatted,
                minimum_formatted=self._format_coin(minimum),
            )

        # Then verify they have sufficient balance
        balance = self.source.balance(kind=self.action)
        balance_needed = self.amount
        if self.action == "withdraw":
            balance_needed += self.ctb.coin.conf["transaction_fee"]
        if balance < balance_needed:
            return self._fail(
                subject,
                "tip-low-balance.tpl",
                action_name=self.action,
                balance_formatted=self._format_coin(balance),
                balance_needed_formatted=self._format_coin(balance_needed),
            )

        if self.action == "tip":
            if self.source == self.destination:
                return self._fail(subject, "cant-send.tpl", destination="yourself")

            if self.ctb.bot == self.destination:
                return self._fail(subject, "cant-send.tpl", destination="the tip bot")

            if not self.destination.is_redditor():
                return self._fail(
                    subject, "not-on-reddit.tpl", destination=self.destination
                )

            if check_action(
                action="tip",
                ctb=self.ctb,
                destination=self.destination,
                source=self.source,
                status="pending",
            ):
                return self._fail(
                    subject, "tip-already-pending.tpl", destination=self.destination
                )

            if not self.destination.is_registered():
                # Perform a pending transfer to escrow
                self.ctb.coin.send(
                    amount=self.amount,
                    destination=self.ctb.bot,
                    source=self.source,
                )
                self.save(status="pending")

                response = self.ctb.jenv.get_template("confirmation.tpl").render(
                    amount_formatted=self._amount_formatted,
                    ctb=self.ctb,
                    destination=self.destination,
                    message=self.message,
                    to_address=False,
                    title="verified^nyan",
                )
                self.source.tell(
                    body=response,
                    message=self.message,
                    reply_to_comment=True,
                    subject="tip pending accept",
                )

                dummy_message = DummyMessage(self.destination, self.message.context)
                response = self.ctb.jenv.get_template("tip-pending.tpl").render(
                    amount_formatted=self._amount_formatted,
                    ctb=self.ctb,
                    dummy_message=dummy_message,
                    source=self.message.author,
                )
                self.destination.tell(body=response, subject="tip pending")
                return False
        elif not self.ctb.coin.validate(address=self.destination):
            return self._fail(subject, "address-invalid.tpl")
        return True


@log_function()
def init_regex(ctb):
    """
    Initialize regular expressions used to match messages and comments
    """
    ctb.runtime["regex"] = []

    for action, action_conf in ctb.conf["regex"]["actions"].items():
        if isinstance(action_conf, str):
            expression = action_conf
            entry = {
                "action": action,
                "regex": re.compile(action_conf, re.IGNORECASE | re.DOTALL),
            }
            entry["regex"] = re.compile(expression, re.IGNORECASE | re.DOTALL)
            logger.debug(f"ADDED REGEX for {action}: {entry['regex'].pattern}")
            ctb.runtime["regex"].append(entry)
            continue

        for _, regex in sorted(action_conf["regex"].items()):
            expression = (
                regex["value"]
                .replace("{REGEX_ADDRESS}", ctb.coin.conf["regex"])
                .replace("{REGEX_AMOUNT}", ctb.conf["regex"]["values"]["amount"])
                .replace("{REGEX_KEYWORD}", ctb.conf["regex"]["values"]["keyword"])
                .replace("{REGEX_USERNAME}", ctb.conf["regex"]["values"]["username"])
                .replace("{BOT_NAME}", f"u/{ctb.conf['reddit']['auth']['username']}")
            )

            entry = {
                "action": action,
                "address": regex["address"],
                "amount": regex["amount"],
                "destination": regex["destination"],
                "keyword": regex["keyword"],
            }

            entry["regex"] = re.compile(expression, re.IGNORECASE | re.DOTALL)
            logger.debug(f"ADDED REGEX for {action}: {entry['regex'].pattern}")
            ctb.runtime["regex"].append(entry)


@log_function()
def eval_message(*, ctb, message):
    for regex in ctb.runtime["regex"]:
        match = regex["regex"].search(message.body)
        if match:
            break
    else:
        logger.debug("eval_message(): no match found")
        return None

    # Match found
    logger.debug("eval_message(): match found")

    # Extract matched fields into variables
    amount = match.group(regex["amount"]) if regex.get("amount") else None
    address = match.group(regex["address"]) if regex.get("address") else None
    destination = (
        match.group(regex["destination"]) if regex.get("destination") else None
    )
    keyword = match.group(regex["keyword"]) if regex.get("keyword") else None

    assert not (address and destination)

    return CtbAction(
        action=regex["action"],
        amount=amount,
        ctb=ctb,
        destination=address or destination,
        keyword=keyword,
        message=message,
    )


def eval_comment(comment, ctb):
    """
    Evaluate comment body and return a CtbAction object if successful
    """
    logger.debug("eval_comment()")

    body = comment.body
    for r in ctb.runtime["regex"]:

        # Skip non-public actions
        if not ctb.conf["regex"]["actions"][r.action].get("public"):
            continue

        # Attempt a match
        m = r.regex.search(body)

        if m:
            # Match found
            logger.debug("eval_comment(): match found")

            # Extract matched fields into variables
            amount = m.group(r.amount) if r.amount > 0 else None
            keyword = m.group(r.keyword) if r.keyword > 0 else None
            to_addr = m.group(r.address) if r.address > 0 else None
            to_user = m.group(r.to_user)[1:] if r.to_user > 0 else None

            # If no destination mentioned, find parent's author
            if not to_user and not to_addr:
                parent = comment.parent()
                if not parent:
                    return None
                to_user = parent.author

            # Check if from_user == to_user
            if to_user and comment.author == to_user:
                logger.warning(
                    "eval_comment(): comment.author == to_user, ignoring comment",
                    comment.author,
                )
                return None

            # Return CtbAction instance with given variables
            logger.debug(
                "eval_comment(): creating action %s: to_user=%s, to_addr=%s, amount=%s, coin=%s"
                % (r.action, to_user, to_addr, amount, r.coin)
            )
            # logger.debug("eval_comment() DONE (yes)")
            return CtbAction(
                atype=r.action,
                message=comment,
                to_user=to_user,
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


def check_action(**kwargs):
    return actions(**kwargs, _check=True)


@log_function("action")
def actions(
    *,
    action=None,
    created_at=None,
    ctb=None,
    destination=None,
    message_id=None,
    source=None,
    status=None,
    _check=False,
):
    arguments = []
    filters = []
    for attribute in ("action", "message_id", "destination", "source", "status"):
        value = locals()[attribute]
        if value:
            arguments.append(value)
            filters.append(f"{attribute} = %s")

    if created_at:
        filters.append(created_at)

    sql_where = f" WHERE {' AND '.join(filters)}"
    sql = f"SELECT * FROM actions{sql_where}"

    logger.debug(
        f"get_actions(): {sql} {arguments}",
    )
    response = ctb.db.execute(sql, arguments)

    if _check:
        return response.rowcount > 0

    if response.rowcount <= 0:
        return []

    results = []
    for row in response:
        logger.debug(f"get_actions(): found {row['message_id']}")
        submission = ctb.reddit.submission(row["message_id"])

        continue

        message = None

        # if submission:
        #     if len(submission.comments) > 0:
        #         message = submission.comments[0]
        #         if not message.author:
        #             logger.warning(
        #                 "get_actions(): could not fetch message.author (deleted?) from message_link %s",
        #                 m["message_link"],
        #             )
        #             logger.warning(
        #                 "get_actions(): setting message.author to original tipper %s",
        #                 m["from_user"],
        #             )
        #     else:
        #         logger.warning(
        #             "get_actions(): could not fetch message (deleted?) from message_link %s",
        #             m["message_link"],
        #         )
        #         logger.warning(
        #             "get_actions(): setting deleted_message_id %s", m["message_id"]
        #         )
        #         deleted_message_id = m["message_id"]
        #         deleted_created_utc = m["created_utc"]
        # else:
        #     logger.warning(
        #         "get_actions(): submission not found for %s . messageid %s",
        #         m["message_link"],
        #         m["message_id"],
        #     )
        #     deleted_message_id = m["message_id"]
        #     deleted_created_utc = m["created_utc"]

        r.append(
            CtbAction(
                atype=atype,
                message=message,
                deleted_message_id=deleted_message_id,
                deleted_created_utc=deleted_created_utc,
                from_user=m["from_user"],
                to_user=m["to_user"],
                to_addr=m["to_addr"] if not m["to_user"] else None,
                coin=m["coin"],
                coin_val=Decimal(m["coin_val"]) if m["coin_val"] else None,
                subr=m["subreddit"],
                ctb=ctb,
            )
        )

    return results
