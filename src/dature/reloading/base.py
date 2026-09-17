"""``ReloadTrigger`` — convenience ABC for triggers that tick on the shared scheduler thread.

Subclassing this is optional: any object satisfying ``ReloadTriggerProtocol`` works as
``reload=``. This ABC exists so a trigger author only has to write ``_poll()`` — the
scheduler registration, start/stop lifecycle, and double-start guard are handled here.
"""

import abc
from collections.abc import Callable
from datetime import timedelta

from dature.reloading.protocol import ReloadContext, ReloadTriggerProtocol
from dature.reloading.scheduler import SCHEDULER, ReloadHandle, Scheduler


class ReloadTrigger(ReloadTriggerProtocol, abc.ABC):
    """Base for triggers that poll on a fixed cadence via a shared ``dature-reload`` thread.

    Args:
        interval: Seconds between polls, as a number or a ``timedelta``. Must be positive.
        scheduler: Scheduler to register on. Defaults to the process-wide ``SCHEDULER`` — pass
            a dedicated ``Scheduler()`` if this trigger's reloads (or a slow ``on_reload``/
            ``on_error`` callback) shouldn't be able to delay every other trigger's.
    """

    def __init__(self, *, interval: float | timedelta, scheduler: Scheduler | None = None) -> None:
        resolved = interval.total_seconds() if isinstance(interval, timedelta) else float(interval)
        if resolved <= 0:
            msg = f"{type(self).__name__} interval must be positive, got {interval!r}"
            raise ValueError(msg)

        self._interval = resolved
        self._scheduler = scheduler if scheduler is not None else SCHEDULER
        self._handle: ReloadHandle | None = None
        self._on_trigger: Callable[[], None] | None = None
        self._started = False

    def start(self, *, on_trigger: Callable[[], None], context: ReloadContext) -> None:
        if self._started:
            msg = f"{type(self).__name__} instance already started — use a separate instance per reload= use"
            raise RuntimeError(msg)

        self._started = True
        self._prepare(context)
        self._on_trigger = on_trigger
        self._handle = self._scheduler.register(self._interval, self._tick)

    def stop(self) -> None:
        if self._handle is not None:
            self._scheduler.unregister(self._handle)
            self._handle = None

    def _prepare(self, context: ReloadContext) -> None:
        """Run synchronously on the caller's thread before scheduling. No-op by default."""

    def _tick(self) -> None:
        if self._poll() and self._on_trigger is not None:
            self._on_trigger()

    @abc.abstractmethod
    def _poll(self) -> bool:
        """Called periodically on the shared scheduler thread. Return True to fire a reload."""
