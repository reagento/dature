"""Heap-based scheduler backing ``reload=`` triggers.

A single daemon thread (``dature-reload``) services every callback registered on one
``Scheduler`` instance, however many triggers use it. This avoids spawning one OS thread per
trigger. The thread starts lazily on the first registration and exits once the heap is empty,
restarting on the next one.

Trade-off: callbacks registered on the same ``Scheduler`` run sequentially on its one thread. A
slow reload for one ``Loader`` delays every other callback sharing that scheduler, and a hung
remote source stalls reloading for everything on it. Sources used with ``reload=`` should apply
their own timeouts; a ``Loader`` that needs isolation from others can be given its own
``Scheduler()`` via ``ReloadTrigger(..., scheduler=...)``.
"""

import heapq
import itertools
import logging
import os
import sys
import threading
import time
from collections.abc import Callable

logger = logging.getLogger("dature")


class ReloadHandle:
    """Opaque handle returned by :meth:`Scheduler.register`, used to later ``unregister``."""

    __slots__ = ("_seq",)

    def __init__(self, seq: int) -> None:
        self._seq = seq


class _Entry:
    __slots__ = ("callback", "cancelled", "interval", "next_fire", "seq")

    def __init__(self, seq: int, next_fire: float, interval: float, callback: Callable[[], None]) -> None:
        self.seq = seq
        self.next_fire = next_fire
        self.interval = interval
        self.callback = callback
        self.cancelled = False


class Scheduler:
    """Heap-based scheduler running every callback registered on it on one shared thread.

    Args:
        restart_after_fork: If True, install an ``os.register_at_fork`` hook that rebuilds
            locking state and restarts the thread in a forked child (see ``_restart_in_child``).
            Off by default: the hook cannot be uninstalled and holds a strong reference to this
            instance forever, so every throwaway ``Scheduler()`` (tests, a caller-owned dedicated
            scheduler) would otherwise leak one hook per instance for the life of the process.
            Only the process-wide default (``SCHEDULER`` below) needs to survive a fork
            (e.g. ``gunicorn --preload``); a scheduler a caller owns and can restart itself
            does not.
    """

    def __init__(self, *, restart_after_fork: bool = False) -> None:
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._heap: list[tuple[float, int]] = []
        self._entries: dict[int, _Entry] = {}
        self._counter = itertools.count()
        self._thread: threading.Thread | None = None
        self._restart_after_fork = restart_after_fork
        self._fork_hook_installed = False

    def register(self, interval: float, callback: Callable[[], None]) -> ReloadHandle:
        """Register *callback* to run every *interval* seconds, first firing after one interval."""
        with self._cond:
            seq = next(self._counter)
            entry = _Entry(seq, time.monotonic() + interval, interval, callback)
            self._entries[seq] = entry
            heapq.heappush(self._heap, (entry.next_fire, seq))
            self._ensure_thread_locked()
            self._cond.notify_all()
        return ReloadHandle(seq)

    def unregister(self, handle: ReloadHandle) -> None:
        """Stop running the callback for *handle*. Idempotent."""
        with self._cond:
            entry = self._entries.pop(handle._seq, None)  # noqa: SLF001
            if entry is not None:
                entry.cancelled = True
            self._cond.notify_all()

    def shutdown(self) -> None:
        """Drop every registration and wait for the background thread to exit. Idempotent.

        Not a test-only escape hatch: since a ``Scheduler`` is now something callers can
        construct themselves (``ReloadTrigger(..., scheduler=Scheduler())``), it should be
        something they can tear down themselves too.
        """
        with self._cond:
            self._heap.clear()
            self._entries.clear()
            self._cond.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=5.0)

    def _ensure_thread_locked(self) -> None:
        if self._restart_after_fork and not self._fork_hook_installed:
            self._fork_hook_installed = True
            if hasattr(os, "register_at_fork"):
                os.register_at_fork(after_in_child=self._restart_in_child)
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="dature-reload", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while True:
            entry = self._wait_for_due_entry()
            if entry is None:
                return
            self._run_guarded(entry.callback)
            with self._cond:
                if not entry.cancelled and entry.seq in self._entries:
                    entry.next_fire = time.monotonic() + entry.interval
                    heapq.heappush(self._heap, (entry.next_fire, entry.seq))
                    self._cond.notify_all()

    def _wait_for_due_entry(self) -> "_Entry | None":
        """Block until an entry is due, popping it. Returns None once the heap is empty."""
        with self._cond:
            while True:
                if not self._heap:
                    self._thread = None
                    return None
                next_fire, seq = self._heap[0]
                entry = self._entries.get(seq)
                if entry is None or entry.cancelled:
                    heapq.heappop(self._heap)
                    continue
                now = time.monotonic()
                if next_fire <= now:
                    heapq.heappop(self._heap)
                    return entry
                self._cond.wait(next_fire - now)

    @staticmethod
    def _run_guarded(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            if not sys.is_finalizing():
                logger.exception("Unhandled exception in a dature reload callback")

    def _restart_in_child(self) -> None:
        """``os.register_at_fork(after_in_child=...)`` hook: rebuild locking state and the thread.

        Threads do not survive ``fork()``: the parent's ``dature-reload`` thread simply does not
        exist in the child, even though this object still claims one is running. Locks/conditions
        may also be held mid-operation at fork time, so they're rebuilt rather than reused.
        """
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._thread = None
        if self._heap:
            with self._cond:
                self._ensure_thread_locked()


# Process-wide default, shared by every trigger that doesn't ask for its own ``Scheduler()``.
# A plain module constant, never rebound — unlike a lazily-built singleton, this needs no
# ``global`` statement: constructing a ``Scheduler`` is cheap (an empty heap, a ``Condition``,
# a counter), so building it at import time installs no thread and no fork hook as a side
# effect of merely ``import dature`` — both are set up lazily inside ``_ensure_thread_locked``,
# only once something actually calls ``register()`` (a trigger's ``start()``).
SCHEDULER = Scheduler(restart_after_fork=True)
