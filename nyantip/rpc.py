from bitcoinrpc.authproxy import AuthServiceProxy


def close_connection(connection, function_name):
    function = getattr(connection, function_name)

    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        finally:
            connection._AuthServiceProxy__conn.close()

    return wrapped


class Rpc:
    def __init__(self, url):
        self._connection = AuthServiceProxy(url)

    def __getattr__(self, attribute):
        return close_connection(connection=self._connection, function_name=attribute)
