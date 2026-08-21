"""TTL / freshness predicate for the cache attached to ``Loader`` instances.

The cache itself lives on the ``Loader`` (see ``dature.loading.loader``).
This module holds only the time helpers — ``cache_now`` (monotonic),
``cache_is_fresh`` (predicate), and ``aligned_now`` (bucket-aligned timestamp
for TTL caches so that all entries sharing the same TTL invalidate at the same
instant).
"""

import time
from datetime import timedelta


def cache_now() -> float:
    return time.monotonic()


def cache_is_fresh(*, cache: bool | timedelta, cached_at: float | None) -> bool:
    if cached_at is None or cache is False:
        return False
    if cache is True:
        return True
    return (cache_now() - cached_at) < cache.total_seconds()


def aligned_now(cache: bool | timedelta) -> float:  # noqa: FBT001
    """Return a monotonic timestamp aligned to the TTL window for cron-style invalidation.

    For ``cache=timedelta(N)``, the returned value is the start of the current
    ``N``-second window. Every entry stored within the same window receives the
    same ``cached_at`` and therefore expires at the same instant.
    """
    now = cache_now()
    if isinstance(cache, timedelta):
        period = cache.total_seconds()
        if period > 0:
            return now - (now % period)
    return now
