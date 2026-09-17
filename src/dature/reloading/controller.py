"""``ReloadController`` — owns a ``Loader``'s ``reload=`` lifecycle.

Everything a ``Loader`` needs to hand off to a background trigger lives here: argument
validation, the weakref-based safety net that keeps the trigger's thread from making the
``Loader`` immortal, start/stop idempotency, and dispatching ``on_reload``/``on_error``.
"""

import logging
import sys
import weakref
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol

from dature.reloading.protocol import ReloadContext, ReloadTriggerProtocol
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import ReloadCallback, ReloadErrorCallback

logger = logging.getLogger("dature")


def validate_reload_args(
    *,
    schema_name: str,
    cache: bool | timedelta,
    reload: ReloadTriggerProtocol | None,
    on_reload: object,
    on_error: object,
) -> None:
    if reload is not None and not isinstance(reload, ReloadTriggerProtocol):
        msg = f"reload= must implement ReloadTriggerProtocol (start/stop), got {reload!r}"
        raise TypeError(msg)
    if reload is None and (on_reload is not None or on_error is not None):
        msg = "on_reload/on_error require reload= to be set"
        raise ValueError(msg)
    if isinstance(cache, timedelta) and reload is not None:
        msg = (
            f"cache={cache!r} and reload= are mutually exclusive: the reload trigger already "
            f"controls the refresh rate, and a TTL on top of it would add a second, blocking "
            f"reload on every bucket boundary. Pass cache=True and set the interval on the trigger."
        )
        raise ValueError(msg)
    if reload is not None and cache is False:
        logger.warning(
            "[%s] reload= has no effect on cached reads with cache=False — on_reload/on_error "
            "will still fire, but every load() call still does a full synchronous load.",
            schema_name,
        )


def file_paths_of(sources: Sequence[SourceProtocol]) -> tuple[Path, ...]:
    return tuple(p for s in sources if isinstance(p := getattr(s, "resolved_file_path", None), Path))


@dataclass(frozen=True, slots=True)
class ReloadOutcome[T]:
    """Result of one trigger-driven reload, reported by the ``Loader`` back to the controller."""

    instance: T
    changed: bool
    error: Exception | None


class ReloadTarget[T](Protocol):
    """What ``ReloadController`` requires from the object it reloads.

    Exists so that the controller depends on this abstraction rather than on ``Loader``:
    the ``loader`` → ``controller`` import stays one-directional, and the owner's type
    stops being ``Any``.
    """

    def _reload_for_trigger(self) -> ReloadOutcome[T]:
        """Perform one forced reload and return its outcome."""
        ...


class ReloadController[T]:
    """Owns one ``Loader``'s ``reload=`` trigger: lifecycle, weak-ref safety, callback dispatch.

    Holds only a ``weakref[ReloadTarget[T]]`` to *target*, not a ``Loader`` — this keeps
    controller.py from importing loader.py — and only a ``weakref`` at all because a strong
    reference (e.g. a bound method passed to ``trigger.start()``) would be held by the
    trigger/scheduler thread for as long as the trigger runs, i.e. forever, making every
    ``Loader`` with ``reload=`` immortal.
    """

    def __init__(
        self,
        target: ReloadTarget[T],
        *,
        trigger: ReloadTriggerProtocol,
        on_reload: ReloadCallback[T] | None,
        on_error: ReloadErrorCallback | None,
        schema_name: str,
    ) -> None:
        self._target: weakref.ref[ReloadTarget[T]] = weakref.ref(target)
        self._trigger = trigger
        self._on_reload = on_reload
        self._on_error = on_error
        self._schema_name = schema_name
        self._started = False
        weakref.finalize(target, trigger.stop)

    def start(self, sources: Sequence[SourceProtocol]) -> None:
        """Start the trigger on the first successful load. Idempotent."""
        if self._started:
            return
        self._started = True
        context = ReloadContext(schema_name=self._schema_name, file_paths=file_paths_of(sources))
        self._trigger.start(on_trigger=self._fire, context=context)

    def stop(self) -> None:
        """Stop the trigger. Idempotent, safe even if never started; always forwarded."""
        self._trigger.stop()
        self._started = False

    def _fire(self) -> None:
        """Called by the trigger, on its own thread. Never raises."""
        target = self._target()
        if target is None:
            self._trigger.stop()
            return
        try:
            outcome = target._reload_for_trigger()  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001 — the background thread must never die
            self._emit(self._on_error, exc)
            return
        if outcome.error is not None:
            self._emit(self._on_error, outcome.error)
        elif outcome.changed:
            self._emit(self._on_reload, outcome.instance)

    def _emit(self, callback: "Callable[[Any], None] | None", value: Any) -> None:  # noqa: ANN401
        if callback is None:
            return
        try:
            callback(value)
        except Exception:
            if not sys.is_finalizing():
                logger.exception("[%s] reload callback raised", self._schema_name)
