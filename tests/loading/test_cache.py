"""Unit tests for src/dature/loading/cache.py."""

import gc
from dataclasses import dataclass
from datetime import timedelta

import pytest
import time_machine

from dature import EnvSource
from dature.loading.cache import (
    CacheEntry,
    cache_get,
    cache_is_fresh,
    cache_now,
    cache_put,
)


@dataclass
class _SchemaA:
    x: int = 0


@dataclass
class _SchemaB:
    y: int = 0


class TestCacheIsFresh:
    @pytest.mark.parametrize(
        ("cache", "advance", "expected"),
        [
            (True, 0.0, True),
            (True, 9_999.0, True),
            (False, 0.0, False),
            (timedelta(seconds=30), 0.0, True),
            (timedelta(seconds=30), 29.999, True),
            (timedelta(seconds=30), 30.0, False),
            (timedelta(seconds=30), 31.0, False),
            (timedelta(0), 0.0, False),
        ],
        ids=[
            "true-immediate",
            "true-far-future",
            "false-disables",
            "ttl-now",
            "ttl-within",
            "ttl-boundary",
            "ttl-expired",
            "ttl-zero",
        ],
    )
    def test_fresh_matrix(
        self,
        time_control: time_machine.Traveller,
        cache: bool | timedelta,
        advance: float,
        expected: bool,
    ) -> None:
        cached_at = cache_now()
        time_control.shift(advance)
        assert cache_is_fresh(cache=cache, cached_at=cached_at) is expected

    @pytest.mark.parametrize("cache", [True, False, timedelta(seconds=30)])
    def test_no_timestamp_is_never_fresh(self, cache: bool | timedelta) -> None:
        assert cache_is_fresh(cache=cache, cached_at=None) is False


class TestCacheGetPut:
    def test_get_without_put_returns_none(self) -> None:
        source = EnvSource()
        assert cache_get(_SchemaA, (source,), cache=True) is None

    def test_round_trip(self) -> None:
        source = EnvSource()
        result = _SchemaA(x=42)

        cache_put(_SchemaA, (source,), result, cache=True)

        assert cache_get(_SchemaA, (source,), cache=True) is result

    def test_get_with_cache_false_returns_none_even_when_stored(self) -> None:
        source = EnvSource()
        cache_put(_SchemaA, (source,), _SchemaA(x=1), cache=True)

        assert cache_get(_SchemaA, (source,), cache=False) is None

    def test_put_with_cache_false_is_noop(self) -> None:
        source = EnvSource()
        cache_put(_SchemaA, (source,), _SchemaA(x=1), cache=False)

        assert cache_get(_SchemaA, (source,), cache=True) is None

    def test_different_schemas_do_not_share(self) -> None:
        source = EnvSource()
        result_a = _SchemaA(x=1)
        result_b = _SchemaB(y=2)

        cache_put(_SchemaA, (source,), result_a, cache=True)
        cache_put(_SchemaB, (source,), result_b, cache=True)

        assert cache_get(_SchemaA, (source,), cache=True) is result_a
        assert cache_get(_SchemaB, (source,), cache=True) is result_b

    def test_different_source_sets_do_not_share(self) -> None:
        source_a = EnvSource()
        source_b = EnvSource()
        result_a = _SchemaA(x=1)
        result_b = _SchemaA(x=2)

        cache_put(_SchemaA, (source_a,), result_a, cache=True)
        cache_put(_SchemaA, (source_b,), result_b, cache=True)

        assert cache_get(_SchemaA, (source_a,), cache=True) is result_a
        assert cache_get(_SchemaA, (source_b,), cache=True) is result_b

    def test_source_order_matters(self) -> None:
        source_a = EnvSource()
        source_b = EnvSource()
        result_ab = _SchemaA(x=1)
        result_ba = _SchemaA(x=2)

        cache_put(_SchemaA, (source_a, source_b), result_ab, cache=True)
        cache_put(_SchemaA, (source_b, source_a), result_ba, cache=True)

        assert cache_get(_SchemaA, (source_a, source_b), cache=True) is result_ab
        assert cache_get(_SchemaA, (source_b, source_a), cache=True) is result_ba

    def test_ttl_expiration_returns_none(self, time_control: time_machine.Traveller) -> None:
        source = EnvSource()
        cache_put(_SchemaA, (source,), _SchemaA(x=1), cache=timedelta(seconds=30))

        time_control.shift(31)
        assert cache_get(_SchemaA, (source,), cache=timedelta(seconds=30)) is None

    def test_overwrite_replaces_entry(self) -> None:
        source = EnvSource()
        first = _SchemaA(x=1)
        second = _SchemaA(x=2)

        cache_put(_SchemaA, (source,), first, cache=True)
        cache_put(_SchemaA, (source,), second, cache=True)

        assert cache_get(_SchemaA, (source,), cache=True) is second


class TestBucketAlignment:
    def test_same_bucket_shares_cached_at(self, time_control: time_machine.Traveller) -> None:
        period = timedelta(seconds=30)

        src_a = EnvSource()
        cache_put(_SchemaA, (src_a,), _SchemaA(x=1), cache=period)

        # Shift forward but stay inside the same bucket.
        remaining = period.total_seconds() - (cache_now() % period.total_seconds())
        time_control.shift(remaining / 2)

        src_b = EnvSource()
        cache_put(_SchemaA, (src_b,), _SchemaA(x=2), cache=period)

        entries = _SchemaA.__dature_cache__
        assert entries[(id(src_a),)].cached_at == entries[(id(src_b),)].cached_at

    def test_same_bucket_invalidates_simultaneously(self, time_control: time_machine.Traveller) -> None:
        period = timedelta(seconds=30)

        src_a = EnvSource()
        cache_put(_SchemaA, (src_a,), _SchemaA(x=1), cache=period)

        remaining = period.total_seconds() - (cache_now() % period.total_seconds())
        time_control.shift(remaining / 2)

        src_b = EnvSource()
        cache_put(_SchemaA, (src_b,), _SchemaA(x=2), cache=period)

        # Both fresh while still inside the bucket.
        assert cache_get(_SchemaA, (src_a,), cache=period) is not None
        assert cache_get(_SchemaA, (src_b,), cache=period) is not None

        # Step past the bucket boundary — both go stale at the same instant.
        time_control.shift(remaining / 2 + 0.001)
        assert cache_get(_SchemaA, (src_a,), cache=period) is None
        assert cache_get(_SchemaA, (src_b,), cache=period) is None


class TestEviction:
    def test_entry_evicted_when_source_gc_d(self) -> None:
        @dataclass
        class LocalSchema:
            x: int = 0

        source = EnvSource()
        cache_put(LocalSchema, (source,), LocalSchema(x=1), cache=True)
        assert cache_get(LocalSchema, (source,), cache=True) is not None

        del source
        gc.collect()

        entries = getattr(LocalSchema, "__dature_cache__", None)
        assert entries == {}

    def test_eviction_only_touches_entries_referencing_gc_d_source(self) -> None:
        @dataclass
        class LocalSchema:
            x: int = 0

        survivor = EnvSource()
        cache_put(LocalSchema, (survivor,), LocalSchema(x=1), cache=True)

        transient = EnvSource()
        cache_put(LocalSchema, (transient,), LocalSchema(x=2), cache=True)

        del transient
        gc.collect()

        assert cache_get(LocalSchema, (survivor,), cache=True) is not None
        entries = LocalSchema.__dature_cache__
        assert len(entries) == 1


def test_cache_entry_is_immutable() -> None:
    entry = CacheEntry(result=object(), cached_at=1.0)
    with pytest.raises(AttributeError):
        entry.cached_at = 2.0  # type: ignore[misc]
