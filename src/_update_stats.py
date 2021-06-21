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

import cointipbot
from ctb import ctb_stats

logging.basicConfig()
logger = logging.getLogger("ctb")
logger.setLevel(logging.DEBUG)

ctb = cointipbot.CointipBot(
    init_coin=False,
    self_checks=False,
)
ctb_stats.update_stats(ctb=ctb)
ctb_stats.update_tips(ctb=ctb)


# for username in ctb.db.execute("SELECT username FROM users ORDER BY username").scalars():
#     ctb_stats.update_user_stats(ctb=ctb, username=username)
