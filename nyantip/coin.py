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

logger = logging.getLogger(__package__)


class Coin:
    def __init__(self, config):
        self.config = config

        logger.debug(f"connecting to {config['name']}")
        self.connection = Bitcoind(config["config_file"])

        logger.info(f"Setting transaction fee of {config['transaction_fee']}")
        try:
            self.connection.settxfee(float(config["transaction_fee"]))
        except ConnectionRefusedError:
            logger.error(
                f"error connecting to {config['name']} ({config['config_file']}) is it running?"
            )
            sys.exit(1)

    def __str__(self):
        return self.config["name"]

    def balance(self, *, minconf, user):
        return self.connection.getbalance(user, minconf).normalize()

    def generate_address(self, *, user):
        passphrase = self.config.get("walletpassphrase")

        if passphrase:
            self.connection.walletpassphrase(passphrase, 1)

        try:
            return self.connection.getnewaddress(user)
        finally:
            if passphrase:
                self.connection.walletlock()

    @log_function("amount", "destination", "source", klass="Coin")
    def send(self, *, amount, destination, source):
        self.connection.move(source.name, destination.name, float(amount))

    @log_function("amount", "address", "source", klass="Coin", log_response=True)
    def transfer(self, *, address, amount, source):
        passphrase = self.config.get("walletpassphrase")

        if passphrase:
            self.connection.walletpassphrase(passphrase, 1)

        try:
            return self.connection.sendfrom(
                source, address, float(amount), self.config["minconf"]["withdraw"]
            )
        finally:
            if passphrase:
                self.connection.walletlock()

    @log_function("address", klass="Coin", log_response=True)
    def validate(self, *, address):
        return self.connection.validateaddress(address).get("isvalid", False)
