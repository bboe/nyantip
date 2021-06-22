#!/usr/bin/python
# -*- coding: utf-8 -*-

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
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote_plus

MAX_WIKI_CONTENT = 511950  # Bytes

logger = logging.getLogger(__package__)


def format_coin(config, quantity):
    return f"{quantity:f} {config['coin']['symbol']}"


def format_value(*, compact=False, config, key, username=None, value):
    if not value:
        return "-"
    if isinstance(value, Decimal):
        return format_coin(config, value.normalize())
    if isinstance(value, datetime):
        return value.isoformat(" ", "minutes")
    if key == "comment":
        return f"[link]({value})"
    if key == "destination" and len(value) > 20:
        return f"[{value[:6]}...{value[-5:]}]({config['coin']['explorer']['address']}{value})"
    if key == "status":
        return "✓" if value == "completed" else value
    if key in ("destination", "source"):
        is_username = username and value.lower() == username.lower()
        user_string = f"**u/{value}**" if is_username else f"u/{value}"
        if compact:
            return user_string
        if not is_username:
            user_string += (
                f"^[[stats]](/r/{config['reddit']['subreddit']}/wiki/stats_{value})"
            )
        return user_string
    return value


def update_stats(nyantip=None):
    lines = []

    for stat, config in sorted(nyantip.config["sql"]["globalstats"].items()):
        logger.debug(f"update_stats(): getting stats for '{stat}'")

        total = nyantip.database.execute(config["query"]).scalar_one()

        lines.append(f"\n\n### {config['name']}\n")
        lines.append(f"{config['description']}: **{total}**\n")

    update_wiki(lines=lines, nyantip=nyantip, page="stats")


def update_tips(nyantip=None):
    tips = [f"### {nyantip.config['coin']['name']} Completed Tips\n"]

    result = nyantip.database.execute(nyantip.config["sql"]["tips"])
    tips.append("|".join(result.keys()))
    tips.append("|".join([":---"] * len(result.keys())))

    for row in result:
        values = []
        for key in result.keys():
            values.append(format_value(config=nyantip.config, key=key, value=row[key]))
        tips.append("|".join(values))

    update_wiki(lines=tips, nyantip=nyantip, page="tips")


def update_user_stats(*, nyantip, username):
    user_stats = [f"### Tipping Summary for u/{username}\n"]

    total = nyantip.database.execute(
        nyantip.config["sql"]["userstats"]["total_tipped"], username
    ).scalar_one_or_none()
    if total:
        user_stats.append(
            f"Total Tipped: {format_coin(nyantip.config, total.normalize())}\n"
        )

    total = nyantip.database.execute(
        nyantip.config["sql"]["userstats"]["total_received"], username
    ).scalar_one_or_none()
    if total:
        user_stats.append(
            f"Total Received: {format_coin(nyantip.config, total.normalize())}\n"
        )

    user_stats.append("#### History\n")
    result = nyantip.database.execute(
        nyantip.config["sql"]["userstats"]["history"], (username, username)
    )
    if result.rowcount <= 0:
        logger.debug(f"update_user_stats(): skipping {username} with no history")
        return

    user_stats.append("|".join(result.keys()))
    user_stats.append("|".join([":---"] * len(result.keys())))

    for row in result:
        history_entry = []
        for key in result.keys():
            history_entry.append(
                format_value(
                    config=nyantip.config,
                    key=key,
                    username=username,
                    value=row[key],
                )
            )
        user_stats.append("|".join(history_entry))

    update_wiki(
        lines=user_stats,
        nyantip=nyantip,
        page=f"stats_{username}",
    )


def update_wiki(*, lines, nyantip, page):
    subreddit = nyantip.config["reddit"]["subreddit"]
    logger.debug(f"update_user_stats(): updating wiki {subreddit}/{page}")
    nyantip.reddit.subreddit(subreddit).wiki[page].edit(content=wiki_fit(lines=lines))


def wiki_fit(*, lines):
    content = None
    end = size = len(lines)
    for i in range(end.bit_length() + 1):
        content = "\n".join(lines[:end])
        size = max(1, round(size / 2))
        if len(quote_plus(content)) <= MAX_WIKI_CONTENT:
            if (
                end == len(lines)
                or len(quote_plus("\n".join(lines[: end + 1]))) > MAX_WIKI_CONTENT
            ):
                return content
            end += size
        else:
            end -= size
    raise Exception(f"wiki_fit didn't terminate in {i} iterations")
