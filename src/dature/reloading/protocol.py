"""Protocol for background reload triggers.

``ReloadTriggerProtocol`` is the minimal interface a ``reload=`` argument must satisfy.
Implementing it directly (without subclassing ``ReloadTrigger``) is fully supported — this
mirrors ``dature.sources.protocol.SourceProtocol`` vs. ``dature.sources.base.source.Source``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ReloadContext:
    """Read-only information handed to a trigger's ``start()``.

    Attributes:
        schema_name: Name of the dataclass being (re)loaded, for error messages.
        file_paths: Resolved file paths of every ``FileSource`` currently in use, in source
            order. Used by ``FileWatchTrigger`` to auto-derive watch paths when ``paths=``
            is not given explicitly.
    """

    schema_name: str
    file_paths: tuple[Path, ...]


@runtime_checkable
class ReloadTriggerProtocol(Protocol):
    """Minimal interface a background reload trigger must satisfy.

    Implement this directly to write a custom trigger without inheriting from
    ``ReloadTrigger`` — any object exposing ``start``/``stop`` with this shape is accepted.
    """

    def start(self, *, on_trigger: Callable[[], None], context: ReloadContext) -> None:
        """Begin watching. Must return immediately and must not call ``on_trigger`` synchronously.

        Args:
            on_trigger: Callback to invoke (from any thread) whenever a reload should happen.
            context: Read-only context about the schema/sources being watched.
        """
        ...

    def stop(self) -> None:
        """Stop watching. Must be idempotent and safe to call even if ``start()`` was never called."""
        ...
