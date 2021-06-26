import logging

from praw.exceptions import RedditAPIException
from prawcore.exceptions import NotFound

from .util import log_function

logger = logging.getLogger(__package__)


class User(object):
    def __init__(self, *, name, nyantip, redditor=None):
        assert isinstance(name, str)
        self.name = name
        self.nyantip = nyantip
        self.redditor = redditor

    def __eq__(self, other):
        return isinstance(other, User) and self.name.lower() == other.name.lower()

    def __repr__(self):
        return f"<User name={self.name}>"

    def __str__(self):
        return self.name

    def balance(self, *, kind):
        return self.nyantip.coin.balance(
            minconf=self.nyantip.config["coin"]["minconf"][kind], user=self.name
        )

    def is_redditor(self):
        if self.redditor is not None:
            return bool(self.redditor)
        self.redditor = self.nyantip.reddit.redditor(self.name)

        try:
            self.redditor.created_utc
        except NotFound:
            self.redditor = False

        return bool(self.redditor)

    def is_registered(self):
        return bool(
            self.nyantip.database.execute(
                "SELECT 1 FROM users WHERE username=%s", self
            ).one_or_none()
        )

    @log_function(klass="User")
    def message(self, *, body, message=None, reply_to_comment=False, subject):
        assert self.redditor is not None

        if message and (reply_to_comment or not message.was_comment):
            assert self.redditor == message.author
            logger.debug(f"({self.redditor}): replying to message {message.id}")
            try:
                message.reply(body)
                return
            except RedditAPIException as exception:
                was_deleted = False
                for subexception in exception.items:
                    if subexception.error_type == "DELETED_COMMENT":
                        was_deleted = True
                        logger.debug(f"({self.redditor}): comment was deleted")
                if not was_deleted:
                    raise

        logger.debug(f"({self.name}): sending message {subject}")
        self.redditor.message(message=body, subject=subject)

    @log_function(klass="User")
    def register(self):
        address = self.nyantip.coin.generate_address(user=self.name)
        logger.info(f"register({self.name}): got {self.nyantip.coin} address {address}")
        self.nyantip.database.execute(
            "INSERT INTO users (address,username) VALUES (%s, %s)", (address, self)
        )
