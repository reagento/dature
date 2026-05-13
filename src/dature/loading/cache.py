"""Schema-attached cache for ``load(...)`` results.

The cache dict lives on the schema class as ``__dature_cache__``, keyed by
``tuple(id(s) for s in sources)``. Both decorator and function modes use the
same storage, so a decorator-applied class and a ``load(..., schema=Cls)`` call
with the same source set share a cache slot. ``weakref.finalize`` evicts entries
when any participating source is garbage-collected (guards against ``id()``
reuse). The cache dies with the schema class — no module-level state.

TTL caching is **bucket-aligned**: when ``cache`` is a ``timedelta``, the
stored ``cached_at`` snaps down to the nearest ``monotonic % period == 0``
boundary. Every class that loads inside the same bucket gets the same
``cached_at`` and therefore invalidates at the exact same instant, regardless
of when the individual ``load(...)`` happened. The first load in a window has
an effectively shortened TTL — this is the standard cron-style trade-off and
matches what users intuitively expect from "invalidate every 15 minutes".
"""

import time
import weakref
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from dature.protocols import DataclassInstance
    from dature.sources.base import Source


_CACHE_ATTR = "__dature_cache__"

type _Key = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CacheEntry:
    result: Any
    cached_at: float


def cache_now() -> float:
    return time.monotonic()


def cache_is_fresh(*, cache: bool | timedelta, cached_at: float | None) -> bool:
    if cached_at is None or cache is False:
        return False
    if cache is True:
        return True
    return (cache_now() - cached_at) < cache.total_seconds()


def cache_get(
    schema: "type[DataclassInstance]",
    sources: "tuple[Source, ...]",
    *,
    cache: bool | timedelta,
) -> "DataclassInstance | None":
    if cache is False:
        return None
    entries = _entries(schema)
    if entries is None:
        return None
    entry = entries.get(_key(sources))
    if entry is None or not cache_is_fresh(cache=cache, cached_at=entry.cached_at):
        return None
    return cast("DataclassInstance", entry.result)


def cache_put(
    schema: "type[DataclassInstance]",
    sources: "tuple[Source, ...]",
    result: "DataclassInstance",
    *,
    cache: bool | timedelta,
) -> None:
    if cache is False:
        return
    entries = _entries(schema)
    if entries is None:
        entries = {}
        setattr(schema, _CACHE_ATTR, entries)
    key = _key(sources)
    entries[key] = CacheEntry(result=result, cached_at=_aligned_now(cache))
    for source in sources:
        weakref.finalize(source, _evict, schema, key)


def _aligned_now(cache: bool | timedelta) -> float:  # noqa: FBT001
    now = cache_now()
    if isinstance(cache, timedelta):
        period = cache.total_seconds()
        if period > 0:
            return now - (now % period)
    return now


def _entries(schema: "type[DataclassInstance]") -> "dict[_Key, CacheEntry] | None":
    return getattr(schema, _CACHE_ATTR, None)


def _evict(schema: "type[DataclassInstance]", key: _Key) -> None:
    entries = _entries(schema)
    if entries is not None:
        entries.pop(key, None)


def _key(sources: "tuple[Source, ...]") -> _Key:
    return tuple(id(s) for s in sources)
