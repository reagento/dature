"""Unit tests for src/dature/loading/cache.py (time predicates)."""

from datetime import timedelta

import pytest
import time_machine

from dature.loading.cache import _aligned_now, cache_is_fresh, cache_now


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


@pytest.mark.usefixtures("time_control")
class TestAlignedNow:
    def test_true_returns_current_monotonic(self) -> None:
        now_before = cache_now()
        aligned = _aligned_now(cache=True)
        assert aligned == now_before

    def test_false_returns_current_monotonic(self) -> None:
        aligned = _aligned_now(cache=False)
        assert aligned == cache_now()

    def test_zero_timedelta_returns_current_monotonic(self) -> None:
        aligned = _aligned_now(timedelta(0))
        assert aligned == cache_now()

    def test_positive_timedelta_snaps_to_bucket_start(self, time_control: time_machine.Traveller) -> None:
        period = timedelta(seconds=30)

        aligned_a = _aligned_now(period)
        remaining = period.total_seconds() - (cache_now() % period.total_seconds())
        time_control.shift(remaining / 2)
        aligned_b = _aligned_now(period)

        assert aligned_a == aligned_b
