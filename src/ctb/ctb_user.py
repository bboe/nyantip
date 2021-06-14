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

from .util import log_function

logger = logging.getLogger("ctb.user")


class CtbUser(object):
    @log_function("name", klass="CtbUser")
    def __init__(self, *, ctb, name, redditor=None):
        self.ctb = ctb
        self.name = name
        self.redditor = redditor

    def __repr__(self):
        return f"<CtbUser name={self.name}>"

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, CtbUser) and self.name.lower() == other.name.lower()

    @log_function("kind", klass="CtbUser")
    def balance(self, *, kind):
        return self.ctb.coin.balance(
            minconf=self.ctb.conf["coin"]["minconf"][kind], user=self.name
        )

    @log_function(klass="CtbUser", log_response=True)
    def is_redditor(self):
        if self.redditor is not None:
            return bool(self.redditor)
        self.redditor = self.ctb.reddit.redditor(self.name)

        try:
            self.redditor.created_utc
        except Exception:
            raise
            self.redditor = False

        return bool(self.redditor)

    @log_function(klass="CtbUser", log_response=True)
    def is_registered(self):
        sql = "SELECT 1 FROM users WHERE username = %s"
        result = self.ctb.db.execute(sql, (self)).fetchone()
        return bool(result)

    @log_function(klass="CtbUser")
    def register(self):
        address = self.ctb.coin.generate_address(user=self.name)
        logger.info(f"register({self.name}): got {self.ctb.coin} address {address}")
        self.ctb.db.execute(
            "INSERT INTO users (address,username) VALUES (%s, %s)", (address, self)
        )

    @log_function(klass="CtbUser")
    def tell(self, *, body, message=None, reply_to_comment=False, subject):
        assert self.redditor is not None

        if message and (reply_to_comment or not message.was_comment):
            assert self.redditor == message.author
            logger.debug(f"tell({self.redditor}): replying to message {message.id}")
            message.reply(body)
            return

        logger.debug(f"tell({self.name}): sending message {subject}")
        self.redditor.message(message=body, subject=subject)
