"""Tests for ``FixedIntervalTrigger`` (reloading/interval.py)."""

from dature.reloading.interval import FixedIntervalTrigger


class TestFixedIntervalTrigger:
    def test_poll_always_true(self) -> None:
        assert FixedIntervalTrigger(interval=60)._poll() is True
