"""RemoteSource: base class for network/API-backed sources."""

import abc
import json
from dataclasses import dataclass
from typing import ClassVar, Final

from dature.errors import SourceLocation
from dature.sources.base.source import Source
from dature.sources.presentation import build_search_path
from dature.type_aliases import JSONValue, NestedConflict

_NOT_FOUND: Final[object] = object()


# --8<-- [start:remote-source]
@dataclass(kw_only=True, repr=False)
class RemoteSource(Source, abc.ABC):
    location_label: ClassVar[str] = "REMOTE"

    # --8<-- [end:remote-source]

    @abc.abstractmethod
    def remote_address(self) -> str: ...

    @abc.abstractmethod
    def _fetch(self) -> JSONValue: ...

    def _load(self) -> JSONValue:
        return self._fetch()

    def __repr__(self) -> str:
        return f"{self.format_name} '{self.remote_address()}'"

    def display_name(self) -> str:
        return self.remote_address()

    @staticmethod
    def _lookup_loaded(field_path: list[str], data: JSONValue) -> "JSONValue | object":
        node: JSONValue = data
        for part in field_path:
            if not isinstance(node, dict) or part not in node:
                return _NOT_FOUND
            node = node[part]
        return node

    def resolve_location(
        self,
        *,
        field_path: list[str],
        nested_conflict: NestedConflict | None,  # noqa: ARG002
        input_value: JSONValue = None,  # noqa: ARG002
        loaded_data: JSONValue | None = None,
    ) -> list[SourceLocation]:
        addr = self.remote_address()
        # ``loaded_data`` holds the raw ``_fetch()`` result (pre-prefix); the schema-side
        # ``field_path`` is already prefix-stripped, so prepend the prefix before looking up.
        search_path = build_search_path(field_path, self.prefix)
        key = ".".join(search_path) if search_path else None
        line_content = [f"{addr}: {key}"] if key else [addr]
        if search_path and loaded_data is not None:
            value = self._lookup_loaded(search_path, loaded_data)
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
