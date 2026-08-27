"""RemoteSource: base class for network/API-backed sources."""

import abc
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Final

from adaptix.provider import Provider

from dature.errors import SourceLocation
from dature.expansion.env_expand import expand_env_vars
from dature.sources.base.source import Source, remote_value_loaders
from dature.sources.presentation import build_search_path
from dature.type_aliases import ExpandEnvVarsMode, JSONValue, NestedConflict

_NOT_FOUND: Final[object] = object()


# --8<-- [start:remote-source]
@dataclass(kw_only=True, repr=False)
class RemoteSource(Source, abc.ABC):
    location_label: str = "REMOTE"

    # --8<-- [end:remote-source]

    @abc.abstractmethod
    def remote_address(self) -> str: ...

    @abc.abstractmethod
    def _fetch(self) -> JSONValue: ...

    def format_loaders(self) -> "list[Provider]":
        return remote_value_loaders()

    def _load(self) -> JSONValue:
        return self._fetch()

    def _decodes_to_strings(self) -> bool:
        """Whether ``_fetch`` yields raw strings that still need scalar inference.

        Overridden by subclasses whose ``decode`` option can select a string decode mode.
        """
        return False

    def _pre_processing(
        self,
        data: JSONValue,
        *,
        resolved_expand: ExpandEnvVarsMode,
    ) -> JSONValue:
        # Parsing must happen after _apply_prefix, not inside _fetch(): _parse_string_values
        # infers scalars aggressively below the top level (see its docstring), and the schema
        # root only reaches depth 0 once the prefix subtree has been navigated into. Doing it
        # before prefix navigation corrupts typed values (e.g. Decimal, long numeric strings)
        # whenever the schema root sits below the document root.
        prefixed = self._apply_prefix(data)
        expanded = expand_env_vars(prefixed, mode=resolved_expand)
        return self._parse_string_values(expanded) if self._decodes_to_strings() else expanded

    def __repr__(self) -> str:
        return f"{self.format_name} '{self.remote_address()}'"

    def display_name(self) -> str:
        return self.remote_address()

    @staticmethod
    def _nest_flat_keys[T](
        items: Iterable[T],
        *,
        key_fn: Callable[[T], str],
        value_fn: Callable[[T], JSONValue],
        prefix: str = "",
        separator: str | None = None,
    ) -> "dict[str, JSONValue]":
        """Turn a flat listing of key/value items into a nested dict, splitting on *separator*.

        *prefix* is stripped from every key first. A key that matches the prefix exactly (no
        remainder) has no leaf name to store a value under and is dropped.
        """
        root: dict[str, JSONValue] = {}
        for item in items:
            remainder = key_fn(item).removeprefix(prefix)
            if separator:
                remainder = remainder.lstrip(separator)
            if not remainder:
                continue
            parts = remainder.split(separator) if separator else [remainder]
            node = root
            for part in parts[:-1]:
                child = node.setdefault(part, {})
                if not isinstance(child, dict):
                    child = {}
                    node[part] = child
                node = child
            node[parts[-1]] = value_fn(item)
        return root

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
                rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=repr)
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
