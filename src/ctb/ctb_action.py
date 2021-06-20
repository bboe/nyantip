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

from praw.models import Comment

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
        keyword=None,
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
            elif isinstance(amount, str):
                assert self.amount.replace(".", "").isnumeric()
                self.amount = Decimal(self.amount)

            assert isinstance(self.amount, Decimal)

    def __str__(self):
        return f"<CtbAction: action={self.action}, amount={self.amount} destination={self.destination} source={self.message.author}>"

    @property
    def _amount_formatted(self):
        return self._format_coin(self.amount)

    def _fail(self, subject, template, save=True, **template_args):
        response = self.ctb.jenv.get_template(template).render(
            ctb=self.ctb, message=self.message, **template_args
        )
        self.source.tell(body=response, message=self.message, subject=subject)
        if save:
            self.save(status="failed")
        return False

    def _format_coin(self, quantity):
        return f"{quantity:f} {self.ctb.conf['coin']['name']}"

    def _safe_send(self, destination, source, amount=None):
        if amount is None:
            amount = self.amount

        try:
            self.ctb.coin.send(
                amount=amount,
                destination=destination,
                source=source,
            )
        except Exception:
            logger.exception(f"action_{self.action}(): failed")
            return self._fail(
                f"{self.action} failed",
                "tip-went-wrong.tpl",
                action_name=self.action,
                amount_formatted=self._amount_formatted,
                destination=None,
                to_address=False,
            )
        return True

    @log_function(klass="CtbAction")
    def action_accept(self):
        pending_actions = actions(
            action="tip", ctb=self.ctb, status="pending", destination=self.source
        )
        if not pending_actions:
            return self._fail("accept failed", "no-pending-tips.tpl")

        if not self.source.is_registered():
            self.source.register()

        users_to_update = set()
        for action in pending_actions:
            if not self._safe_send(
                destination=self.source, source=self.ctb.bot, amount=action.amount
            ):
                self.save(status="failed")
                return
            users_to_update.add(action.source.name)
            action.save(status="completed")

            response = self.ctb.jenv.get_template("confirmation.tpl").render(
                amount_formatted=action._amount_formatted,
                ctb=self.ctb,
                destination=action.destination,
                message=action.message,
                title="verified^nyan",
                to_address=False,
                transaction_id=None,
            )
            action.source.tell(
                body=response,
                message=action.message,
                reply_to_comment=True,
                subject="tip succeeded",
            )

        self.save(status="completed")
        self.action = "info"
        self.action_info(save=False)

        ctb_stats.update_user_stats(ctb=self.ctb, username=self.source)
        for username in users_to_update:
            ctb_stats.update_user_stats(ctb=self.ctb, username=username)

    @log_function(klass="CtbAction")
    def action_decline(self):
        pending_actions = actions(
            action="tip", ctb=self.ctb, status="pending", destination=self.source
        )
        if not pending_actions:
            return self._fail("decline failed", "no-pending-tips.tpl")

        for action in pending_actions:
            if not self._safe_send(
                destination=action.source, source=self.ctb.bot, amount=action.amount
            ):
                self.save(status="failed")
                return
            action.save(status="declined")

            response = self.ctb.jenv.get_template("confirmation.tpl").render(
                amount_formatted=action._amount_formatted,
                ctb=self.ctb,
                destination=action.destination,
                message=action.message,
                title="declined^nyan",
                to_address=False,
                transaction_id=None,
            )
            action.source.tell(
                body=response, message=action.message, subject="tip succeeded"
            )

        self.save(status="completed")
        response = self.ctb.jenv.get_template("pending-tips-declined.tpl").render(
            ctb=self.ctb, message=self.message
        )
        self.source.tell(body=response, message=self.message, subject="decline failed")

    @log_function(klass="CtbAction")
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
        self.message.reply(response)
        self.save(status="completed")

    @log_function(klass="CtbAction")
    def action_info(self, save=True):
        if not self.source.is_registered():
            return self._fail("info failed", "not-registered.tpl", save=save)

            response = self.ctb.jenv.get_template().render(
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

        if save:
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
        self.action_info(save=False)

    @log_function(klass="CtbAction")
    def action_tip(self):
        assert self.destination
        if not self.validate():
            return

        if not self._safe_send(destination=self.destination, source=self.source):
            return
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

        ctb_stats.update_user_stats(ctb=self.ctb, username=self.source)
        ctb_stats.update_user_stats(ctb=self.ctb, username=self.destination)

    @log_function(klass="CtbAction")
    def action_withdraw(self):
        assert self.destination
        if not self.validate():
            return

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

    @log_function(klass="CtbAction")
    def expire(self):
        if not self._safe_send(
            destination=self.source, source=self.ctb.bot, amount=self.amount
        ):
            return
        self.save(status="expired")

        response = self.ctb.jenv.get_template("confirmation.tpl").render(
            amount_formatted=self._amount_formatted,
            ctb=self.ctb,
            destination=self.destination,
            message=self.message,
            title="expired^nyan",
            to_address=False,
            transaction_id=None,
        )
        self.source.tell(body=response, message=self.message, subject="tip expired")

    @log_function(klass="CtbAction")
    def perform(self):
        if self.action == "accept":
            self.action_accept()
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
        else:
            assert self.action == "withdraw"
            self.action_withdraw()

    @log_function("status", klass="CtbAction")
    def save(self, *, status):
        was_comment = isinstance(self.message, Comment) or self.message.was_comment
        result = self.ctb.db.execute(
            "REPLACE INTO actions (action, amount, destination, message_id, message_kind, message_timestamp, source, status, transaction_id) VALUES (%s, %s, %s, %s, %s, FROM_UNIXTIME(%s), %s, %s, %s)",
            (
                self.action,
                self.amount,
                self.destination,
                self.message.id,
                "comment" if was_comment else "message",
                self.message.created_utc,
                self.source.name,
                status,
                self.transaction_id,
            ),
        )
        assert 1 <= result.rowcount <= 2

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
                    title="pending accept^nyan",
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


def check_action(**kwargs):
    return actions(**kwargs, _check=True)


@log_function("actions")
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

    logger.debug(f"actions(): {sql} {arguments}")
    response = ctb.db.execute(sql, arguments)

    if _check:
        return response.rowcount > 0

    if response.rowcount <= 0:
        return []

    results = []
    for row in response:
        logger.debug(f"actions(): found {row['message_id']}")

        amount = row["amount"]
        if amount is not None:
            amount = amount.normalize()

        if row["message_kind"] == "comment":
            message = ctb.reddit.comment(row["message_id"])
        else:
            message = ctb.reddit.inbox.message(row["message_id"])

        results.append(
            CtbAction(
                action=action,
                amount=amount,
                ctb=ctb,
                destination=row["destination"],
                message=message,
            )
        )

    return results
