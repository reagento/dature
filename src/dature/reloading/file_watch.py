"""``FileWatchTrigger`` — reload when a watched config file changes on disk.

Requires ``watchdog`` (extra ``dature[watch]``); by default shares one process-wide
``Observer`` across every ``FileWatchTrigger`` instance.
"""

import threading
from pathlib import Path
from typing import Any

from dature._deps import require_dep
from dature.reloading.base import ReloadTrigger
from dature.reloading.protocol import ReloadContext
from dature.reloading.scheduler import Scheduler


class _DirtyHandler:
    """Marks *dirty* when a watched file is created, modified, or (atomically) replaced.

    Duck-types watchdog's ``FileSystemEventHandler`` (a ``dispatch(event)`` method) instead of
    subclassing it, so this class needs no import from ``watchdog`` — it can live at module
    scope even though ``watchdog`` itself is only ever imported lazily, inside
    ``_SharedObserver.get()``.
    """

    def __init__(self, names: frozenset[str], dirty: threading.Event) -> None:
        self._names = names
        self._dirty = dirty

    def dispatch(self, event: Any) -> None:  # noqa: ANN401
        if event.event_type in ("created", "modified", "moved"):
            path = getattr(event, "dest_path", None) or event.src_path
            if Path(path).name in self._names:
                self._dirty.set()


class _SharedObserver:
    """Lazily-built, process-wide watchdog ``Observer``, shared by every trigger that doesn't
    bring its own. Lazy because building it imports ``watchdog`` — ``import dature`` must not.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._observer: Any = None

    def get(self) -> Any:  # noqa: ANN401
        with self._lock:
            if self._observer is None:
                from watchdog.observers import Observer  # noqa: PLC0415

                observer = Observer()
                observer.daemon = True
                observer.start()
                self._observer = observer
            return self._observer


# Same rationale as ``SCHEDULER`` in reloading/scheduler.py — a module constant, never rebound.
SHARED_OBSERVER = _SharedObserver()


class FileWatchTrigger(ReloadTrigger):
    """Reload when any watched file is created, modified, or (atomically) replaced.

    Requires the optional ``watchdog`` package (``pip install 'dature[watch]'``) — raises
    ``ImportError`` from the first ``load()`` if it isn't installed.

    Args:
        paths: Files to watch. If omitted, derived from the ``resolved_file_path`` of every
            ``FileSource`` in use at ``start()`` time.
        debounce: Seconds to wait after a change before firing, to coalesce editor save bursts.
        observer: watchdog ``Observer`` to schedule watches on. Defaults to a process-wide
            shared one — pass your own for isolation, or to inject a fake in tests.
        scheduler: See :class:`ReloadTrigger`.
    """

    def __init__(
        self,
        *,
        paths: "list[Path | str] | None" = None,
        debounce: float = 0.5,
        observer: Any = None,  # noqa: ANN401
        scheduler: Scheduler | None = None,
    ) -> None:
        self._explicit_paths = tuple(Path(p) for p in paths) if paths else None
        self._observer = observer
        self._dirty = threading.Event()
        self._paths: tuple[Path, ...] = ()
        super().__init__(interval=debounce, scheduler=scheduler)

    def _prepare(self, context: ReloadContext) -> None:
        require_dep("watchdog", "watch")

        candidates = self._explicit_paths or context.file_paths
        paths = tuple(p for p in candidates if p.parent.exists())
        if not paths:
            msg = (
                f"FileWatchTrigger for {context.schema_name!r} has no file paths to watch "
                f"(no FileSource with a resolved path). Pass paths=[...] explicitly."
            )
            raise ValueError(msg)
        self._paths = paths

        observer = self._observer if self._observer is not None else SHARED_OBSERVER.get()
        names = frozenset(p.name for p in paths)
        handler = _DirtyHandler(names, self._dirty)
        for directory in {p.parent for p in paths}:
            observer.schedule(handler, str(directory), recursive=False)

    def _poll(self) -> bool:
        if self._dirty.is_set():
            self._dirty.clear()
            return True
        return False
