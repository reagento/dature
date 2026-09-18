"""Tests for ``ReloadController`` and its helpers (reloading/controller.py).

``Loader`` is exercised end-to-end (through ``reload=``) in ``tests/loading/test_loader.py``.
These tests cover the controller in isolation — no real ``Loader`` involved.
"""

import gc
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest

from dature.reloading.controller import ReloadController, ReloadOutcome, file_paths_of, validate_reload_args
from dature.reloading.protocol import ReloadContext
from dature.sources.protocol import SourceProtocol


class _FakeTrigger:
    """Minimal ``ReloadTriggerProtocol`` double that records calls and exposes ``fire()``."""

    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0
        self.context: ReloadContext | None = None
        self._on_trigger: Callable[[], None] | None = None

    def start(self, *, on_trigger: Callable[[], None], context: ReloadContext) -> None:
        self.start_count += 1
        self.context = context
        self._on_trigger = on_trigger

    def stop(self) -> None:
        self.stop_count += 1

    def fire(self) -> None:
        assert self._on_trigger is not None, "fire() called before start()"
        self._on_trigger()


class _Target:
    """Stand-in for a ``Loader`` — implements ``ReloadTarget`` without inheriting from it."""

    def __init__(
        self,
        outcome: "ReloadOutcome[str] | None" = None,
        raises: "Exception | None" = None,
    ) -> None:
        self.calls: list[None] = []
        self._outcome = outcome
        self._raises = raises

    def _reload_for_trigger(self) -> "ReloadOutcome[str]":
        self.calls.append(None)
        if self._raises is not None:
            raise self._raises
        if self._outcome is None:
            pytest.fail("_reload_for_trigger called unexpectedly")
        return self._outcome


@dataclass
class _Source:
    resolved_file_path: Path | None = None


def _sources(*items: object) -> Sequence[SourceProtocol]:
    return cast("Sequence[SourceProtocol]", items)


class TestValidateReloadArgs:
    def test_accepts_protocol_conforming_trigger(self) -> None:
        validate_reload_args(schema_name="Cfg", cache=True, reload=_FakeTrigger(), on_reload=None, on_error=None)

    def test_rejects_non_protocol_trigger(self) -> None:
        with pytest.raises(TypeError, match="must implement ReloadTriggerProtocol"):
            validate_reload_args(schema_name="Cfg", cache=True, reload=object(), on_reload=None, on_error=None)

    @pytest.mark.parametrize("kwarg", ["on_reload", "on_error"])
    def test_rejects_callbacks_without_trigger(self, kwarg: str) -> None:
        callbacks = {"on_reload": None, "on_error": None, kwarg: object()}

        with pytest.raises(ValueError, match="on_reload/on_error require reload="):
            validate_reload_args(schema_name="Cfg", cache=True, reload=None, **callbacks)

    def test_rejects_ttl_cache_combined_with_reload(self) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            validate_reload_args(
                schema_name="Cfg", cache=timedelta(seconds=30), reload=_FakeTrigger(), on_reload=None, on_error=None
            )

    def test_warns_when_reload_has_no_effect_on_cache_false(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="dature"):
            validate_reload_args(schema_name="Cfg", cache=False, reload=_FakeTrigger(), on_reload=None, on_error=None)

        assert [r.getMessage() for r in caplog.records] == [
            (
                "[Cfg] reload= has no effect on cached reads with cache=False — on_reload/on_error "
                "will still fire, but every load() call still does a full synchronous load."
            )
        ]


class TestFilePathsOf:
    def test_keeps_only_sources_with_a_resolved_file_path(self, tmp_path: Path) -> None:
        file_source = _Source(resolved_file_path=tmp_path / "a.json")
        no_path_source = _Source(resolved_file_path=None)
        non_file_source = object()

        paths = file_paths_of(_sources(file_source, no_path_source, non_file_source))

        assert paths == (tmp_path / "a.json",)


class TestReloadController:
    def _make(
        self,
        *,
        target: _Target,
        on_reload: "Callable[[str], None] | None" = None,
        on_error: "Callable[[Exception], None] | None" = None,
    ) -> tuple[_Target, _FakeTrigger, ReloadController[str]]:
        trigger = _FakeTrigger()
        controller = ReloadController(
            target,
            trigger=trigger,
            on_reload=on_reload,
            on_error=on_error,
            schema_name="Cfg",
        )
        return target, trigger, controller

    def test_start_is_idempotent(self) -> None:
        _target, trigger, controller = self._make(target=_Target())

        controller.start(_sources())
        controller.start(_sources())

        assert trigger.start_count == 1

    def test_stop_forwards_every_call(self) -> None:
        _target, trigger, controller = self._make(target=_Target())

        controller.stop()
        controller.stop()

        assert trigger.stop_count == 2

    def test_start_passes_resolved_file_paths_in_context(self, tmp_path: Path) -> None:
        _target, trigger, controller = self._make(target=_Target())
        source = _Source(resolved_file_path=tmp_path / "a.json")

        controller.start(_sources(source))

        assert trigger.context == ReloadContext(schema_name="Cfg", file_paths=(tmp_path / "a.json",))

    def test_fire_emits_on_reload_when_instance_changed(self) -> None:
        received: list[str] = []
        _target, trigger, controller = self._make(
            target=_Target(outcome=ReloadOutcome(instance="new", changed=True, error=None)),
            on_reload=received.append,
        )
        controller.start(_sources())

        trigger.fire()

        assert received == ["new"]

    def test_fire_is_silent_when_instance_is_unchanged(self) -> None:
        received: list[str] = []
        _target, trigger, controller = self._make(
            target=_Target(outcome=ReloadOutcome(instance="same", changed=False, error=None)),
            on_reload=received.append,
        )
        controller.start(_sources())

        trigger.fire()

        assert received == []

    def test_fire_emits_on_error_instead_of_on_reload_on_stale_fallback(self) -> None:
        reload_received: list[str] = []
        error_received: list[Exception] = []
        stale_exc = RuntimeError("source broken")
        _target, trigger, controller = self._make(
            target=_Target(outcome=ReloadOutcome(instance="stale", changed=True, error=stale_exc)),
            on_reload=reload_received.append,
            on_error=error_received.append,
        )
        controller.start(_sources())

        trigger.fire()

        assert reload_received == []
        assert error_received == [stale_exc]

    def test_fire_emits_on_error_when_run_reload_raises(self) -> None:
        error_received: list[Exception] = []
        _target, trigger, controller = self._make(
            target=_Target(raises=RuntimeError("boom")),
            on_error=error_received.append,
        )
        controller.start(_sources())

        trigger.fire()

        assert len(error_received) == 1
        assert str(error_received[0]) == "boom"

    def test_fire_logs_but_swallows_a_broken_callback(self, caplog: pytest.LogCaptureFixture) -> None:
        def _broken_on_reload(_value: str) -> None:
            msg = "callback exploded"
            raise RuntimeError(msg)

        _target, trigger, controller = self._make(
            target=_Target(outcome=ReloadOutcome(instance="new", changed=True, error=None)),
            on_reload=_broken_on_reload,
        )
        controller.start(_sources())

        with caplog.at_level(logging.ERROR, logger="dature"):
            trigger.fire()  # must not raise

        assert [r.getMessage() for r in caplog.records] == ["[Cfg] reload callback raised"]
        assert caplog.records[0].exc_info is not None
        assert caplog.records[0].exc_info[0] is RuntimeError

    def test_fire_stops_trigger_instead_of_calling_run_reload_once_owner_is_gone(self) -> None:
        def _make_and_drop() -> _FakeTrigger:
            _, trigger, controller = self._make(target=_Target())
            controller.start(_sources())
            return trigger

        trigger = _make_and_drop()
        gc.collect()
        stop_count_after_gc = trigger.stop_count

        trigger.fire()

        assert trigger.stop_count == stop_count_after_gc + 1
