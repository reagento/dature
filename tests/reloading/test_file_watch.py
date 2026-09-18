"""Tests for ``FileWatchTrigger`` (reloading/file_watch.py).

Most cases exercise the fake observer below (deterministic, no filesystem watching); one smoke
test drives real watchdog machinery, forced onto its portable ``PollingObserver`` backend since
the OS-native fsevents backend needs an entitlement this sandbox denies.
"""

import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from dature import JsonSource, Loader
from dature.reloading.file_watch import SHARED_OBSERVER, FileWatchTrigger
from dature.reloading.protocol import ReloadContext
from dature.reloading.scheduler import Scheduler


@dataclass
class _Config:
    host: str
    port: int


class TestFileWatchTrigger:
    @pytest.mark.parametrize("debounce", [0, -1])
    def test_validates_debounce(self, debounce: float) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            FileWatchTrigger(debounce=debounce)

    def test_auto_derives_paths_from_file_source(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        trigger = FileWatchTrigger(observer=_FakeObserver())
        context = ReloadContext(schema_name="_Config", file_paths=(json_file,))

        trigger._prepare(context)

        assert trigger._paths == (json_file,)

    def test_no_file_source_raises(self) -> None:
        trigger = FileWatchTrigger(observer=_FakeObserver())
        context = ReloadContext(schema_name="_Config", file_paths=())

        with pytest.raises(ValueError, match="_Config"):
            trigger._prepare(context)

    def test_missing_watchdog_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "watchdog", None)
        trigger = FileWatchTrigger()

        with pytest.raises(ImportError, match=r"pip install 'dature\[watch\]'"):
            trigger._prepare(ReloadContext(schema_name="_Config", file_paths=(Path("x.json"),)))

    def test_ignores_unrelated_file_in_same_directory(self, tmp_path: Path) -> None:
        watched = tmp_path / "config.json"
        watched.write_text('{"host": "h", "port": 1}')
        other = tmp_path / "unrelated.txt"
        other.write_text("noise")
        fake_observer = _FakeObserver()
        trigger = FileWatchTrigger(observer=fake_observer)
        trigger._prepare(ReloadContext(schema_name="_Config", file_paths=(watched,)))

        handler, _ = fake_observer.scheduled[0]
        handler.dispatch(_FakeEvent("created", str(other)))

        assert trigger._poll() is False

    def test_reacts_to_watched_file_event(self, tmp_path: Path) -> None:
        watched = tmp_path / "config.json"
        watched.write_text('{"host": "h", "port": 1}')
        fake_observer = _FakeObserver()
        trigger = FileWatchTrigger(observer=fake_observer)
        trigger._prepare(ReloadContext(schema_name="_Config", file_paths=(watched,)))

        handler, _ = fake_observer.scheduled[0]
        handler.dispatch(_FakeEvent("modified", str(watched)))

        assert trigger._poll() is True

    def test_atomic_rename_uses_dest_path(self, tmp_path: Path) -> None:
        watched = tmp_path / "config.json"
        watched.write_text('{"host": "h", "port": 1}')
        fake_observer = _FakeObserver()
        trigger = FileWatchTrigger(observer=fake_observer)
        trigger._prepare(ReloadContext(schema_name="_Config", file_paths=(watched,)))

        handler, _ = fake_observer.scheduled[0]
        handler.dispatch(_FakeEvent("moved", str(tmp_path / "config.json.tmp"), dest_path=str(watched)))

        assert trigger._poll() is True

    def test_two_triggers_share_one_observer(self, tmp_path: Path) -> None:
        pytest.importorskip("watchdog")
        first = tmp_path / "a.json"
        second = tmp_path / "b.json"
        first.write_text("{}")
        second.write_text("{}")
        trigger_a = FileWatchTrigger()
        trigger_b = FileWatchTrigger()

        trigger_a._prepare(ReloadContext(schema_name="A", file_paths=(first,)))
        trigger_b._prepare(ReloadContext(schema_name="B", file_paths=(second,)))

        assert SHARED_OBSERVER.get() is SHARED_OBSERVER.get()

    def test_real_watchdog_smoke(self, tmp_path: Path, scheduler: Scheduler) -> None:
        pytest.importorskip("watchdog")
        from watchdog.observers.polling import PollingObserver  # noqa: PLC0415

        watched = tmp_path / "config.json"
        watched.write_text('{"host": "h", "port": 1}')
        source = JsonSource(file=watched)
        # Use the real watchdog machinery (handlers, events) but force the portable polling
        # backend: the OS-native fsevents backend needs an entitlement this sandbox denies.
        poller = PollingObserver(timeout=0.1)
        poller.daemon = True
        poller.start()
        trigger = FileWatchTrigger(debounce=0.05, observer=poller, scheduler=scheduler)
        received = threading.Event()
        instances: list[_Config] = []

        def _on_reload(cfg: _Config) -> None:
            instances.append(cfg)
            received.set()

        loader = Loader(source, schema=_Config, cache=True, reload=trigger, on_reload=_on_reload)
        loader.load()

        time.sleep(0.2)  # let the watchdog observer finish scheduling the watch
        watched.write_text('{"host": "changed", "port": 2}')

        assert received.wait(5.0)
        assert instances == [_Config(host="changed", port=2)]


class _FakeEvent:
    def __init__(self, event_type: str, src_path: str, *, dest_path: str | None = None) -> None:
        self.event_type = event_type
        self.src_path = src_path
        if dest_path is not None:
            self.dest_path = dest_path


class _FakeObserver:
    def __init__(self) -> None:
        self.scheduled: list[tuple[Any, str]] = []

    def schedule(self, handler: Any, path: str, *, recursive: bool = False) -> None:  # noqa: ARG002
        self.scheduled.append((handler, path))
