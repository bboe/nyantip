import logging
import time

logger = logging.getLogger(__package__)


class DummyMessage:
    def __init__(self, author, context):
        self.author = author
        self.context = context


def log_function(*fields, klass=None, log_method=None, log_response=False):
    if not log_method:
        log_method = logger.debug

    def decorator(function):
        def wrapped(*args, **kwargs):
            arguments = ",".join(
                f"{field}={kwargs[field]!r}" for field in fields if kwargs.get(field)
            )

            start = time.time() * 1000
            response = function(*args, **kwargs)
            duration = time.time() * 1000 - start

            description = f"{function.__name__}({arguments})"
            if klass:
                description = f"{klass}.{description}"
            if log_response:
                description = f"{description} = {response!r}"

            log_method(f"{description} in {duration:0.4f} ms")
            return response

        return wrapped

    return decorator
