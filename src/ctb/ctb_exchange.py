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

import http.client
import json
import logging

logger = logging.getLogger("ctb.exchange")


class CtbExchange(object):
    """
    Exchange class for cointip bot
    """

    conf = None

    def __init__(self, _conf=None):
        """
        Initialize CtbExchange with given parameters.
            _conf is an exchange config dictionary defind in conf/exchanges.yml
        """

        if (
            not _conf
            or "urlpaths" not in _conf
            or "jsonpaths" not in _conf
            or "coinlist" not in _conf
            or "fiatlist" not in _conf
        ):
            raise Exception("__init__(): _conf is empty or invalid")

        self.conf = _conf

        # Convert coinlist and fiatlist values to lowercase
        self.conf["coinlist"] = map(lambda x: x.lower(), self.conf["coinlist"])
        self.conf["fiatlist"] = map(lambda x: x.lower(), self.conf["fiatlist"])

        logger.debug("__init__(): initialized exchange %s" % self.conf["domain"])

    def supports(self, _name=None):
        """
        Return True if exchange supports given coin/fiat _name
        """

        if not isinstance(_name, str):
            raise Exception("supports(): _name is empty or wrong type")

        name = str(_name).lower()

        if name in self.conf["coinlist"] or name in self.conf["fiatlist"]:
            # logger.debug("supports(%s): YES" % name)
            return True
        else:
            # logger.debug("supports(%s): NO" % name)
            return False

    def supports_pair(self, _name1=None, _name2=None):
        """
        Return true of exchange supports given coin/fiat pair
        """

        return self.supports(_name=_name1) and self.supports(_name=_name2)

    def get_ticker_value(self, _name1=None, _name2=None):
        """
        Return (float) ticker value for given pair
        """

        if _name1 == _name2:
            return float(1)

        if not self.supports_pair(_name1=_name1, _name2=_name2):
            raise Exception(
                "get_ticker_value(%s, %s, %s): pair not supported"
                % (self.conf["domain"], _name1, _name2)
            )

        results = []
        for myurlpath in self.conf["urlpaths"]:
            for myjsonpath in self.conf["jsonpaths"]:

                toreplace = {
                    "{THING_FROM}": _name1.upper()
                    if self.conf["uppercase"]
                    else _name1.lower(),
                    "{THING_TO}": _name2.upper()
                    if self.conf["uppercase"]
                    else _name2.lower(),
                }
                for t in toreplace:
                    myurlpath = myurlpath.replace(t, toreplace[t])
                    myjsonpath = myjsonpath.replace(t, toreplace[t])

                try:
                    logger.debug(
                        "get_ticker_value(%s, %s, %s): calling %s to get %s...",
                        self.conf["domain"],
                        _name1,
                        _name2,
                        myurlpath,
                        myjsonpath,
                    )
                    if self.conf["https"]:
                        connection = http.client.HTTPSConnection(self.conf["domain"])
                        connection.request("GET", myurlpath, {}, {})
                    else:
                        connection = http.client.HTTPConnection(self.conf["domain"])
                        connection.request("GET", myurlpath)
                    response = json.loads(connection.getresponse().read())
                    result = xpath_get(response, myjsonpath)
                    logger.debug(
                        "get_ticker_value(%s, %s, %s): result: %.6f",
                        self.conf["domain"],
                        _name1,
                        _name2,
                        float(result),
                    )
                    results.append(float(result))
                except (http.client.HTTPException, Exception) as e:
                    logger.error(
                        "get_ticker_value(%s, %s, %s): %s",
                        self.conf["domain"],
                        _name1,
                        _name2,
                        e,
                    )
                    return None

        # Return average of all responses
        return sum(results) / float(len(results))


def xpath_get(mydict, path):
    elem = mydict
    try:
        for x in path.strip(".").split("."):
            try:
                x = int(x)
                elem = elem[x]
            except ValueError:
                elem = elem.get(x)
    except Exception:
        pass

    return elem
