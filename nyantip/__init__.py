import argparse
import logging

from .bot import NyanTip
from .const import __version__  # noqa

logging.basicConfig(
    datefmt="%H:%M:%S",
    format="%(asctime)s %(levelname)-8s %(name)-12s %(message)s",
)
logging.getLogger("BitcoinRPC").setLevel(logging.DEBUG)


def main():
    parser = argparse.ArgumentParser(
        description="Run nyantip bot or associated utilities"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="", title="subcommands")
    subparsers.add_parser("backup", help="Backup config, database, and wallet")

    arguments = parser.parse_args()
    if arguments.command == "backup":
        NyanTip().backup()
    else:
        NyanTip().run()
