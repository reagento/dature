"""Drop-in replacement for testcontainers' deprecated ``@wait_container_is_ready`` decorator.

Retries ``func`` until it stops raising one of *transient_exceptions*, using the same
timeout/poll-interval config testcontainers itself reads from the environment.
"""

import time
from collections.abc import Callable

from testcontainers.core.config import testcontainers_config


def retry_until_ready[T](func: Callable[[], T], *transient_exceptions: type[Exception]) -> T:
    """Call ``func()`` until it succeeds, retrying on *transient_exceptions*."""
    start = time.time()
    while True:
        try:
            return func()
        except transient_exceptions as exc:
            if time.time() - start > testcontainers_config.timeout:
                msg = f"Wait time ({testcontainers_config.timeout}s) exceeded for {func!r}"
                raise TimeoutError(msg) from exc
            time.sleep(testcontainers_config.sleep_time)
