"""Tests for the shared ``dature-reload`` scheduler (reloading/scheduler.py).

The only test module that uses real threads and real timing — every reload= integration test
elsewhere drives ``Loader._reload_once`` directly via a fake trigger instead. Tests here use
short intervals and bounded ``Event.wait()`` calls, never ``time.sleep()`` as a synchronization
mechanism, so they stay fast and don't flake under load. Each test gets its own private
``Scheduler`` via the ``scheduler`` fixture, so they never touch the process-wide default.
"""

import threading
import time

import pytest

from dature.reloading.scheduler import Scheduler


class TestScheduler:
    def test_single_thread_for_many_triggers(self, scheduler: Scheduler) -> None:
        before = sum(1 for t in threading.enumerate() if t.name == "dature-reload")

        for _ in range(5):
            scheduler.register(60, lambda: None)

        after = sum(1 for t in threading.enumerate() if t.name == "dature-reload")

        assert after - before == 1

    def test_scheduler_fires_registered_entry(self, scheduler: Scheduler) -> None:
        fired = threading.Event()

        scheduler.register(0.01, fired.set)

        assert fired.wait(2.0)

    def test_unregister_stops_firing(self, scheduler: Scheduler) -> None:
        count = 0
        lock = threading.Lock()
        fired = threading.Event()

        def _tick() -> None:
            nonlocal count
            with lock:
                count += 1
            fired.set()

        handle = scheduler.register(0.01, _tick)
        assert fired.wait(2.0)
        scheduler.unregister(handle)
        fired.clear()

        # No further fire should arrive once unregistered.
        assert not fired.wait(0.2)
        with lock:
            observed = count
        time.sleep(0.05)
        with lock:
            assert count == observed

    def test_entry_exception_does_not_kill_scheduler(self, scheduler: Scheduler) -> None:
        survivor_fired = threading.Event()

        def _broken() -> None:
            msg = "boom"
            raise RuntimeError(msg)

        scheduler.register(0.01, _broken)
        scheduler.register(0.01, survivor_fired.set)

        assert survivor_fired.wait(2.0)
        # A second round proves the thread kept running after the first entry raised.
        survivor_fired.clear()
        assert survivor_fired.wait(2.0)

    def test_register_wakes_sleeping_thread(self, scheduler: Scheduler) -> None:
        scheduler.register(60, lambda: None)
        fired = threading.Event()

        scheduler.register(0.01, fired.set)

        # If registering didn't wake the sleeping thread, it would wait for the 60s entry first.
        assert fired.wait(2.0)

    def test_stop_joins_thread_promptly(self, scheduler: Scheduler) -> None:
        handle = scheduler.register(0.01, lambda: None)

        scheduler.unregister(handle)

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            thread = scheduler._thread
            if thread is None or not thread.is_alive():
                return
            time.sleep(0.01)
        pytest.fail("dature-reload thread did not exit after the last entry was unregistered")
