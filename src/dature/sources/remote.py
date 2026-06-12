"""RemoteSource: base class for network/API-backed sources."""

import abc
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Final

from dature.errors import SourceLocation
from dature.sources.base import Source
from dature.sources.presentation import build_search_path
from dature.type_aliases import JSONValue, NestedConflict

_NOT_FOUND: Final[object] = object()


# --8<-- [start:remote-source]
@dataclass(kw_only=True, repr=False)
class RemoteSource(Source, abc.ABC):
    location_label: ClassVar[str] = "REMOTE"

    _loaded_cache: JSONValue | None = field(default=None, init=False, repr=False)
    # --8<-- [end:remote-source]

    @abc.abstractmethod
    def remote_address(self) -> str: ...

    @abc.abstractmethod
    def _fetch(self) -> JSONValue: ...

    def _load(self) -> JSONValue:
        result = self._fetch()
        self._loaded_cache = result
        return result

    def __repr__(self) -> str:
        return f"{self.format_name} '{self.remote_address()}'"

    def display_name(self) -> str:
        return self.remote_address()

    def file_display(self) -> str | None:
        return self.remote_address()

    def file_path_for_errors(self) -> Path | None:
        return None

    def _lookup_loaded(self, field_path: list[str]) -> "JSONValue | object":
        if self._loaded_cache is None:
            return _NOT_FOUND
        node: JSONValue = self._loaded_cache
        for part in field_path:
            if not isinstance(node, dict) or part not in node:
                return _NOT_FOUND
            node = node[part]
        return node

    def resolve_location(
        self,
        *,
        field_path: list[str],
        file_content: str | None,  # noqa: ARG002
        nested_conflict: NestedConflict | None,  # noqa: ARG002
        input_value: JSONValue = None,  # noqa: ARG002
    ) -> list[SourceLocation]:
        addr = self.remote_address()
        # ``_loaded_cache`` holds the raw ``_fetch()`` result (pre-prefix); the schema-side
        # ``field_path`` is already prefix-stripped, so prepend the prefix before looking up.
        search_path = build_search_path(field_path, self.prefix)
        key = ".".join(search_path) if search_path else None
        line_content = [f"{addr}: {key}"] if key else [addr]
        if search_path:
            value = self._lookup_loaded(search_path)
            if value is not _NOT_FOUND:
                rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                line_content = [f"{addr}: {key} = {rendered}"]
        return [
            SourceLocation(
                location_label=self.location_label,
                file_path=None,
                line_range=None,
                line_content=line_content,
                env_var_name=None,
                line_carets=None,
            ),
        ]
