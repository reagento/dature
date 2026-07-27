import abc
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal, cast

from adaptix import loader
from adaptix.provider import Provider

from dature._deps import require_dep
from dature.coercion import (
    bytearray_from_string,
    date_passthrough,
    datetime_passthrough,
    none_from_empty_string,
    optional_from_empty_string,
)
from dature.coercion.toml_ import time_passthrough
from dature.errors import LineRange
from dature.sources.base import FileSource
from dature.type_aliases import FILE_LIKE_TYPES, FileOrStream, JSONValue

type _TomlVersionStr = Literal["1.0.0", "1.1.0"]

try:
    from toml_rs._toml_rs import KeyMeta  # pyright: ignore[reportAssignmentType]
except ImportError:  # pragma: no cover  -- ``KeyMeta`` lives in the .pyi stub only

    class KeyMeta(dict[str, object]):  # type: ignore[no-redef]
        ...


@dataclass(kw_only=True, repr=False)
class _BaseTomlSource(FileSource, abc.ABC):
    @abc.abstractmethod
    def _toml_version(self) -> _TomlVersionStr:
        """Return the TOML spec version this source parses.

        Subclasses return a string literal rather than ``toml_rs._lib.TomlVersion``
        directly so this module can be imported without the ``toml`` extra.
        """

    def _load_file(self, path: FileOrStream) -> JSONValue:
        require_dep("toml_rs", "toml")
        import toml_rs  # noqa: PLC0415

        if isinstance(path, FILE_LIKE_TYPES):
            content = path.read()
            if isinstance(content, bytes):
                content = content.decode()
            return cast("JSONValue", toml_rs.loads(content, toml_version=self._toml_version()))
        with path.open(encoding=self.encoding) as file:
            return cast("JSONValue", toml_rs.loads(file.read(), toml_version=self._toml_version()))

    def build_line_index(self, content: str) -> dict[tuple[str, ...], LineRange] | None:
        return _build_toml_line_map(content, self._toml_version())

    def format_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_passthrough),
            loader(bytearray, bytearray_from_string),
            loader(type(None), none_from_empty_string),
            loader(str | None, optional_from_empty_string),
            loader(Any, optional_from_empty_string),
        ]


@dataclass(kw_only=True, repr=False)
class Toml10Source(_BaseTomlSource):
    format_name: str = "toml1.0"

    def _toml_version(self) -> _TomlVersionStr:
        return "1.0.0"


@dataclass(kw_only=True, repr=False)
class Toml11Source(_BaseTomlSource):
    format_name: str = "toml1.1"

    def _toml_version(self) -> _TomlVersionStr:
        return "1.1.0"


def _build_toml_line_map(content: str, toml_version: _TomlVersionStr) -> dict[tuple[str, ...], LineRange]:
    require_dep("toml_rs", "toml")
    import toml_rs  # noqa: PLC0415

    doc = toml_rs.load_with_metadata(content, toml_version=toml_version)
    line_map: dict[tuple[str, ...], LineRange] = {}
    # doc.meta["nodes"] is always the real toml_rs.KeyMeta at runtime (require_dep above
    # already guarantees toml_rs is installed); pyright's declared type for KeyMeta here
    # is the try/except stub union, hence the mismatch.
    _walk_toml_nodes(doc.meta["nodes"], (), line_map)  # pyright: ignore[reportArgumentType]
    return line_map


def _walk_toml_nodes(
    nodes: dict[str, KeyMeta],
    prefix: tuple[str, ...],
    line_map: dict[tuple[str, ...], LineRange],
) -> None:
    for name, node in nodes.items():
        if not isinstance(node, dict):
            continue
        path = (*prefix, name)
        if "key" not in node:
            _walk_toml_nodes(cast("dict[str, KeyMeta]", node), path, line_map)
            continue
        _process_toml_leaf_or_inline_table(node, path, line_map)


def _process_toml_leaf_or_inline_table(
    node: KeyMeta,
    path: tuple[str, ...],
    line_map: dict[tuple[str, ...], LineRange],
) -> None:
    value = node.get("value")
    value_line = node.get("value_line")

    if value_line is not None:
        start = node["key_line"]
        if isinstance(value_line, tuple):
            end = value_line[1]
        else:
            end = value_line
        # KeyMeta's fallback stub types values as `object`; the real toml_rs.KeyMeta
        # stub (used whenever toml_rs is actually installed) declares them as int.
        line_map[path] = LineRange(start=start, end=end)  # pyright: ignore[reportArgumentType]
        if isinstance(value, dict):
            _walk_toml_nodes(cast("dict[str, KeyMeta]", value), path, line_map)
        return

    if isinstance(value, list):
        for idx, element in enumerate(value):
            if not isinstance(element, dict):
                continue
            inner = element.get("value")
            if isinstance(inner, dict):
                indexed_path = (*path, str(idx))
                _walk_toml_nodes(cast("dict[str, KeyMeta]", inner), indexed_path, line_map)
