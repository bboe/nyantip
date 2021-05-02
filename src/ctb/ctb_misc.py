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
import time
from socket import timeout

from praw.errors import RateLimitExceeded
from requests.exceptions import ConnectionError, HTTPError, Timeout

logger = logging.getLogger("ctb.misc")


def praw_call(prawFunc, *extraArgs, **extraKwArgs):
    """
    Call prawFunc() with extraArgs and extraKwArgs
    Retry if Reddit is down
    """

    while True:

        try:
            res = prawFunc(*extraArgs, **extraKwArgs)
            return res

        except (HTTPError, ConnectionError, Timeout, RateLimitExceeded, timeout) as e:
            if str(e) == "403 Client Error: Forbidden":
                logger.warning("praw_call(): 403 forbidden")
                return False
            if str(e) == "404 Client Error: Not Found":
                logger.warning("praw_call(): 404 not found")
                return False
            logger.warning("praw_call(): Reddit is down (%s), sleeping...", e)
            time.sleep(30)

    return True


def permalink(message):
    """
    Return permalink if possible for message.
    """
    return getattr(message, "_fast_permalink", None)


def reddit_get_parent_author(comment, reddit, ctb):
    """
    Return author of comment's parent comment
    """
    logger.debug("reddit_get_parent_author()")

    while True:

        try:
            parentcomment = reddit.get_info(thing_id=comment.parent_id)
            if hasattr(parentcomment, "author") and parentcomment.author:
                logger.debug(
                    "reddit_get_parent_author(%s) -> %s",
                    comment.id,
                    parentcomment.author.name,
                )
                return parentcomment.author.name
            else:
                logger.warning(
                    "reddit_get_parent_author(%s): parent comment was deleted",
                    comment.id,
                )
                return None

        except IndexError as e:
            logger.warning("reddit_get_parent_author(): couldn't get author: %s", e)
            return None
        except (RateLimitExceeded, timeout) as e:
            logger.warning(
                "reddit_get_parent_author(): Reddit is down (%s), sleeping...", e
            )
            time.sleep(ctb.conf.misc.times.sleep_seconds)
        except HTTPError as e:
            logger.warning(
                "reddit_get_parent_author(): thread or comment not found (%s)", e
            )
            return None

    logger.error("reddit_get_parent_author(): returning None (should not get here)")
    return None


def get_value(conn, param0=None):
    """
    Fetch a value from t_values table
    """
    logger.debug("get_value()")

    if param0 is None:
        raise Exception("get_value(): param0 is None")

    value = None
    sql = "SELECT value0 FROM t_values WHERE param0 = %s"

    try:

        mysqlrow = conn.execute(sql, (param0)).fetchone()
        if mysqlrow is None:
            logger.error(
                "get_value(): query <%s> didn't return any rows", sql % (param0)
            )
            return None
        value = mysqlrow["value0"]

    except Exception as e:
        logger.error("get_value(): error executing query <%s>: %s", sql % (param0), e)
        raise

    logger.debug("get_value() DONE (%s)", value)
    return value


def set_value(conn, param0=None, value0=None):
    """
    Set a value in t_values table
    """
    logger.debug("set_value(%s, %s)", param0, value0)

    if param0 is None or value0 is None:
        raise Exception("set_value(): param0 is None or value0 is None")
    sql = "REPLACE INTO t_values (param0, value0) VALUES (%s, %s)"

    try:

        mysqlexec = conn.execute(sql, (param0, value0))
        if mysqlexec.rowcount <= 0:
            logger.error(
                "set_value(): query <%s> didn't affect any rows", sql % (param0, value0)
            )
            return False

    except Exception as e:
        logger.error(
            "set_value: error executing query <%s>: %s", sql % (param0, value0), e
        )
        raise

    logger.debug("set_value() DONE")
    return True
