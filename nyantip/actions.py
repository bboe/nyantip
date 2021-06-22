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
from decimal import Decimal

from praw.models import Comment

from . import stats, user
from .util import DummyMessage

logger = logging.getLogger(__package__)


class Action(object):
    def __init__(
        self,
        *,
        action,
        nyantip,
        message,
        amount=None,
        destination=None,
        keyword=None,
    ):

        self.action = action
        self.amount = amount
        self.message = message
        self.nyantip = nyantip
        self.source = user.User(
            nyantip=nyantip, name=message.author.name, redditor=message.author
        )
        self.transaction_id = None

        if action == "tip":
            self.destination = user.User(name=destination, nyantip=nyantip)
        else:
            self.destination = destination

        if self.action in ["tip", "withdraw"]:
            if keyword:
                assert self.amount is None
                value = self.nyantip.config["keywords"][keyword.lower()]
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
        return f"<Action: action={self.action}, amount={self.amount} destination={self.destination} source={self.message.author}>"

    @property
    def _amount_formatted(self):
        return self._format_coin(self.amount)

    def _fail(self, subject, template, save=True, **template_args):
        response = self.nyantip.templates.get_template(template).render(
            config=self.nyantip.config, message=self.message, **template_args
        )
        self.source.message(body=response, message=self.message, subject=subject)
        if save:
            self.save(status="failed")
        return False

    def _format_coin(self, quantity):
        return f"{quantity:f} {self.nyantip.config['coin']['name']}"

    def _safe_send(self, destination, source, amount=None):
        if amount is None:
            amount = self.amount

        try:
            self.nyantip.coin.send(
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

    def action_accept(self):
        pending_actions = actions(
            action="tip",
            nyantip=self.nyantip,
            status="pending",
            destination=self.source,
        )
        if not pending_actions:
            return self._fail("accept failed", "no-pending-tips.tpl")

        if not self.source.is_registered():
            self.source.register()

        users_to_update = set()
        for action in pending_actions:
            if not self._safe_send(
                destination=self.source, source=self.nyantip.bot, amount=action.amount
            ):
                self.save(status="failed")
                return
            users_to_update.add(action.source.name)
            action.save(status="completed")

            response = self.nyantip.templates.get_template("confirmation.tpl").render(
                amount_formatted=action._amount_formatted,
                config=self.nyantip.config,
                destination=action.destination,
                message=action.message,
                title="verified^nyan",
                to_address=False,
                transaction_id=None,
            )
            action.source.message(
                body=response,
                message=action.message,
                reply_to_comment=True,
                subject="tip succeeded",
            )

        self.save(status="completed")
        self.action = "info"
        self.action_info(save=False)

        stats.update_user_stats(nyantip=self.nyantip, username=self.source.name)
        for username in users_to_update:
            stats.update_user_stats(nyantip=self.nyantip, username=username)

    def action_decline(self):
        pending_actions = actions(
            action="tip",
            nyantip=self.nyantip,
            status="pending",
            destination=self.source,
        )
        if not pending_actions:
            return self._fail("decline failed", "no-pending-tips.tpl")

        for action in pending_actions:
            if not self._safe_send(
                destination=action.source, source=self.nyantip.bot, amount=action.amount
            ):
                self.save(status="failed")
                return
            action.save(status="declined")

            response = self.nyantip.templates.get_template("confirmation.tpl").render(
                amount_formatted=action._amount_formatted,
                config=self.nyantip.config,
                destination=action.destination,
                message=action.message,
                title="declined^nyan",
                to_address=False,
                transaction_id=None,
            )
            action.source.message(
                body=response, message=action.message, subject="tip declined"
            )

        self.save(status="completed")
        response = self.nyantip.templates.get_template(
            "pending-tips-declined.tpl"
        ).render(
            config=self.nyantip.config,
            message=self.message,
        )
        self.source.message(
            body=response, message=self.message, subject="declined succeeded"
        )

    def action_history(self):
        history = []

        response = self.nyantip.database.execute(
            self.nyantip.config["sql"]["history"], (self.source, self.source)
        )
        for row in response:
            history_entry = []
            for key in response.keys():
                history_entry.append(
                    stats.format_value(
                        config=self.nyantip.config,
                        compact=True,
                        key=key,
                        username=self.source.name,
                        value=row[key],
                    )
                )
            history.append(history_entry)

        if history:
            response = self.nyantip.templates.get_template("history.tpl").render(
                config=self.nyantip.config,
                history=history,
                keys=response.keys(),
                message=self.message,
            )
        else:
            response = self.nyantip.templates.get_template("history-empty.tpl").render(
                config=self.nyantip.config,
                message=self.message,
            )
        self.message.reply(response)
        self.save(status="completed")

    def action_info(self, save=True):
        if not self.source.is_registered():
            return self._fail("info failed", "not-registered.tpl", save=save)

        balance = self.nyantip.coin.balance(
            minconf=self.nyantip.coin.config["minconf"]["tip"],
            user=self.source.name,
        )
        address = self.nyantip.database.execute(
            "SELECT address FROM users WHERE username = %s", self.source
        ).scalar_one()

        response = self.nyantip.templates.get_template("info.tpl").render(
            action=self,
            address=address,
            balance=balance,
            config=self.nyantip.config,
            message=self.message,
        )
        self.message.reply(response)

        if save:
            self.save(status="completed")

        return True

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

    def action_tip(self):
        assert self.destination
        if not self.validate():
            return

        if not self._safe_send(destination=self.destination, source=self.source):
            return
        self.save(status="completed")

        response = self.nyantip.templates.get_template("confirmation.tpl").render(
            amount_formatted=self._amount_formatted,
            config=self.nyantip.config,
            destination=self.destination,
            message=self.message,
            title="verified^nyan",
            to_address=False,
            transaction_id=None,
        )
        self.source.message(
            body=response,
            message=self.message,
            reply_to_comment=True,
            subject="tip succeeded",
        )

        dummy_message = DummyMessage(self.destination, self.message.context)
        response = self.nyantip.templates.get_template("tip-received.tpl").render(
            amount_formatted=self._amount_formatted,
            config=self.nyantip.config,
            dummy_message=dummy_message,
            source=self.message.author,
        )
        self.destination.message(body=response, subject="tip received")

        stats.update_user_stats(nyantip=self.nyantip, username=self.source.name)
        stats.update_user_stats(nyantip=self.nyantip, username=self.destination.name)

    def action_withdraw(self):
        assert self.destination
        if not self.validate():
            return

        try:
            self.transaction_id = self.nyantip.coin.transfer(
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
        response = self.nyantip.templates.get_template("confirmation.tpl").render(
            amount_formatted=self._amount_formatted,
            config=self.nyantip.config,
            destination=self.destination,
            message=self.message,
            title="verified^nyan",
            to_address=True,
            transaction_id=self.transaction_id,
        )
        self.source.message(
            body=response, message=self.message, subject="withdraw succeeded"
        )

    def expire(self):
        if not self._safe_send(
            destination=self.source, source=self.nyantip.bot, amount=self.amount
        ):
            return
        self.save(status="expired")

        response = self.nyantip.templates.get_template("confirmation.tpl").render(
            amount_formatted=self._amount_formatted,
            config=self.nyantip.config,
            destination=self.destination,
            message=self.message,
            title="expired^nyan",
            to_address=False,
            transaction_id=None,
        )
        self.source.message(body=response, message=self.message, subject="tip expired")

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

    def save(self, *, status):
        permalink = None
        if isinstance(self.message, Comment):
            self.message.refresh()
            permalink = self.message.permalink

        result = self.nyantip.database.execute(
            "REPLACE INTO actions (action, amount, destination, message_id, message_timestamp, path, source, status, transaction_id) VALUES (%s, %s, %s, %s, FROM_UNIXTIME(%s), %s, %s, %s, %s)",
            (
                self.action,
                self.amount,
                self.destination,
                self.message.id,
                self.message.created_utc,
                permalink,
                self.source.name,
                status,
                self.transaction_id,
            ),
        )
        assert 1 <= result.rowcount <= 2

    def validate(self):
        subject = f"{self.action} failed"

        # First see if the author is registered
        if not self.source.is_registered():
            return self._fail(subject, "not-registered.tpl")

        # Second ensure the amount is larger than the necessary minimum
        minimum = self.nyantip.coin.config[f"minimum_{self.action}"]
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
            balance_needed += self.nyantip.coin.config["transaction_fee"]
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

            if self.nyantip.bot == self.destination:
                return self._fail(subject, "cant-send.tpl", destination="me")

            if not self.destination.is_redditor():
                return self._fail(
                    subject, "not-on-reddit.tpl", destination=self.destination
                )

            if check_action(
                action="tip",
                destination=self.destination,
                nyantip=self.nyantip,
                source=self.source,
                status="pending",
            ):
                return self._fail(
                    subject, "tip-already-pending.tpl", destination=self.destination
                )

            if not self.destination.is_registered():
                # Perform a pending transfer to escrow
                self.nyantip.coin.send(
                    amount=self.amount,
                    destination=self.nyantip.bot,
                    source=self.source,
                )
                self.save(status="pending")

                response = self.nyantip.templates.get_template(
                    "confirmation.tpl"
                ).render(
                    amount_formatted=self._amount_formatted,
                    config=self.nyantip.config,
                    destination=self.destination,
                    message=self.message,
                    title="pending accept^nyan",
                    to_address=False,
                    transaction_id=None,
                )
                self.source.message(
                    body=response,
                    message=self.message,
                    reply_to_comment=True,
                    subject="tip pending accept",
                )

                dummy_message = DummyMessage(self.destination, self.message.context)
                response = self.nyantip.templates.get_template(
                    "tip-pending.tpl"
                ).render(
                    amount_formatted=self._amount_formatted,
                    config=self.nyantip.config,
                    dummy_message=dummy_message,
                    source=self.message.author,
                )
                self.destination.message(body=response, subject="tip pending")
                return False
        elif not self.nyantip.coin.validate(address=self.destination):
            return self._fail(
                subject, "address-invalid.tpl", destination=self.destination
            )
        return True


def actions(
    *,
    action=None,
    created_at=None,
    destination=None,
    message_id=None,
    nyantip=None,
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

    logger.debug(f"query: {sql} {arguments}")
    response = nyantip.database.execute(sql, arguments)

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

        if row["path"] is not None:
            message = nyantip.reddit.comment(row["message_id"])
        else:
            message = nyantip.reddit.inbox.message(row["message_id"])

        results.append(
            Action(
                action=action,
                amount=amount,
                destination=row["destination"],
                message=message,
                nyantip=nyantip,
            )
        )

    return results


def check_action(**kwargs):
    return actions(**kwargs, _check=True)
