import logging

from .bot import NyanTip
from .const import __version__

logging.basicConfig(
    datefmt="%H:%M:%S",
    format="%(asctime)s %(levelname)-8s %(name)-12s %(message)s",
)
logging.getLogger("bitcoin").setLevel(logging.INFO)


def main():
    NyanTip().run()
