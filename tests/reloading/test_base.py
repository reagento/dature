"""Tests for the ``ReloadTrigger`` ABC (reloading/base.py)."""

import pytest

from dature.reloading.base import ReloadTrigger
from dature.reloading.protocol import ReloadContext
from dature.reloading.scheduler import Scheduler


class _Trigger(ReloadTrigger):
    def _poll(self) -> bool:
        return False


class TestReloadTrigger:
    @pytest.mark.parametrize("interval", [0, -1])
    def test_validates_interval(self, interval: float) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            _Trigger(interval=interval)

    def test_double_start_raises(self, scheduler: Scheduler) -> None:
        trigger = _Trigger(interval=60, scheduler=scheduler)
        context = ReloadContext(schema_name="_Config", file_paths=())

        trigger.start(on_trigger=lambda: None, context=context)

        with pytest.raises(RuntimeError, match="already started"):
            trigger.start(on_trigger=lambda: None, context=context)

        trigger.stop()

    def test_stop_without_start_is_a_noop(self, scheduler: Scheduler) -> None:
        _Trigger(interval=60, scheduler=scheduler).stop()
