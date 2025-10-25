import signal
from contextlib import contextmanager


class TimeoutExceptionError(Exception):
    """Exception raised when a timeout occurs."""

    pass


@contextmanager
def time_limit(seconds):
    """
    Context manager that raises a TimeoutExceptionError if the code block takes longer than the specified seconds.

    Args:
        seconds (int): Maximum number of seconds the code block can run before timing out.

    Raises:
        TimeoutExceptionError: If the code block takes longer than the specified seconds to execute.
    """

    def signal_handler(signum, frame):  # noqa: ARG001
        raise TimeoutExceptionError("Timed out!")

    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
