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
import sys

from pifkoin.bitcoind import Bitcoind

from .util import log_function

logger = logging.getLogger("ctb.coin")


class CtbCoin:
    def __init__(self, conf):
        self.conf = conf

        logger.debug("connecting to %s...", self.conf["name"])
        self.connection = Bitcoind(self.conf["config_file"])

        logger.info(f"Setting tx fee of {self.conf['transaction_fee']:f}")
        try:
            self.connection.settxfee(float(self.conf["transaction_fee"]))
        except ConnectionRefusedError:
            logger.exception(
                "error connecting to %s using %s: %s",
                self.conf["name"],
                self.conf["config_file"],
            )
            sys.exit(1)

    def __str__(self):
        return self.conf["name"]

    @log_function("user", klass="CtbCoin")
    def balance(self, *, minconf, user):
        return self.connection.getbalance(user, minconf).normalize()

    def generate_address(self, *, user):
        passphrase = self.conf.get("walletpassphrase")

        if passphrase:
            self.connection.walletpassphrase(passphrase, 1)

        try:
            return self.connection.getnewaddress(user)
        finally:
            if passphrase:
                self.connection.walletlock()

    @log_function("amount", "destination", "source", klass="CtbCoin")
    def send(self, *, amount, destination, source):
        self.connection.move(source.name, destination.name, amount)

    @log_function("amount", "address", "source", klass="CtbCoin", log_response=True)
    def transfer(self, *, address, amount, source):
        passphrase = self.conf.get("walletpassphrase")

        if passphrase:
            self.connection.walletpassphrase(passphrase, 1)

        try:
            return self.connection.sendfrom(
                source, address, amount, self.conf["minconf"]["withdraw"]
            )
        finally:
            if passphrase:
                self.connection.walletlock()

    @log_function("address", klass="CtbCoin", log_response=True)
    def validate(self, *, address):
        return self.connection.validateaddress(address).get("isvalid", False)
