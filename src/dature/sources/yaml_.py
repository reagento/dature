import abc
from dataclasses import dataclass
from datetime import date, datetime, time
from io import StringIO
from typing import cast

from adaptix import loader
from adaptix.provider import Provider

from dature._deps import require_dep
from dature.coercion import (
    bytearray_from_string,
    date_passthrough,
    datetime_passthrough,
    time_from_string,
)
from dature.coercion.yaml_ import time_from_int
from dature.errors import LineRange
from dature.sources.base import FileSource
from dature.type_aliases import FILE_LIKE_TYPES, FileOrStream, JSONValue

try:
    from ruamel.yaml.comments import CommentedMap, CommentedSeq  # pyright: ignore[reportAssignmentType]
    from ruamel.yaml.docinfo import Version  # pyright: ignore[reportAssignmentType]
    from ruamel.yaml.scalarstring import ScalarString  # pyright: ignore[reportAssignmentType]
except ImportError:  # pragma: no cover

    class _LineCol:
        data: dict[object, tuple[int, int, int, int]]

    class CommentedMap(dict[str, object]):  # type: ignore[no-redef]
        lc: _LineCol

    class CommentedSeq(list[object]):  # type: ignore[no-redef]
        ...

    class ScalarString(str):  # type: ignore[no-redef]
        __slots__ = ()

    class Version:  # type: ignore[no-redef]
        def __init__(self, *args: int) -> None: ...


@dataclass(kw_only=True, repr=False)
class _BaseYamlSource(FileSource, abc.ABC):
    @abc.abstractmethod
    def _yaml_version(self) -> tuple[int, int]:
        """Return the (major, minor) YAML version this source parses.

        Subclasses return a tuple instead of ``ruamel.yaml.docinfo.Version``
        directly so this module can be imported without the ``yaml`` extra
        installed.
        """

    def _load_file(self, path: FileOrStream) -> JSONValue:
        require_dep("ruamel.yaml", "yaml")
        from ruamel.yaml import YAML  # noqa: PLC0415

        yaml = YAML(typ="safe")
        yaml.version = Version(*self._yaml_version())
        if isinstance(path, FILE_LIKE_TYPES):
            return cast("JSONValue", yaml.load(path))
        with path.open(encoding=self.encoding) as file:
            return cast("JSONValue", yaml.load(file))

    def build_line_index(self, content: str) -> dict[tuple[str, ...], LineRange] | None:
        return _build_yaml_line_map(content, Version(*self._yaml_version()))


@dataclass(kw_only=True, repr=False)
class Yaml11Source(_BaseYamlSource):
    format_name: str = "yaml1.1"

    def _yaml_version(self) -> tuple[int, int]:
        return (1, 1)

    def format_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_from_int),
            loader(bytearray, bytearray_from_string),
        ]


@dataclass(kw_only=True, repr=False)
class Yaml12Source(_BaseYamlSource):
    format_name: str = "yaml1.2"

    def _yaml_version(self) -> tuple[int, int]:
        return (1, 2)

    def format_loaders(self) -> list[Provider]:
        return [
            loader(date, date_passthrough),
            loader(datetime, datetime_passthrough),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]


def _build_yaml_line_map(content: str, yaml_version: Version) -> dict[tuple[str, ...], LineRange]:
    require_dep("ruamel.yaml", "yaml")
    from ruamel.yaml import YAML  # noqa: PLC0415

    yaml = YAML(typ="rt")
    yaml.version = yaml_version
    data = yaml.load(StringIO(content))
    if not isinstance(data, CommentedMap):
        return {}
    lines = content.splitlines()
    line_map: dict[tuple[str, ...], LineRange] = {}
    _walk_yaml_mapping(data, (), line_map, lines, len(lines))
    return line_map


def _last_non_empty_yaml_line_before(lines: list[str], before_0based: int, after_0based: int) -> int:
    """Returns 1-based line number of last non-empty line in [after_0based, before_0based)."""
    for i in range(before_0based - 1, after_0based - 1, -1):
        if lines[i].strip():
            return i + 1
    return after_0based + 1


def _walk_yaml_mapping(
    mapping: CommentedMap,
    parent_path: tuple[str, ...],
    line_map: dict[tuple[str, ...], LineRange],
    lines: list[str],
    parent_end_1based: int,
) -> None:
    keys = list(mapping.keys())
    lc_data = mapping.lc.data

    for idx, key in enumerate(keys):
        key_str = str(key)
        current_path = (*parent_path, key_str)

        key_line_0, _key_col, val_line_0, _val_col = lc_data[key]
        start_1based = key_line_0 + 1

        value = mapping[key]

        if isinstance(value, CommentedMap):
            if idx + 1 < len(keys):
                next_key = keys[idx + 1]
                next_key_line_0 = lc_data[next_key][0]
                end_1based = _last_non_empty_yaml_line_before(lines, next_key_line_0, key_line_0)
            else:
                end_1based = _last_non_empty_yaml_line_before(lines, parent_end_1based, key_line_0)

            line_map[current_path] = LineRange(start=start_1based, end=end_1based)
            _walk_yaml_mapping(value, current_path, line_map, lines, end_1based)

        elif isinstance(value, CommentedSeq):
            if idx + 1 < len(keys):
                next_key = keys[idx + 1]
                next_key_line_0 = lc_data[next_key][0]
                end_1based = _last_non_empty_yaml_line_before(lines, next_key_line_0, key_line_0)
            else:
                end_1based = _last_non_empty_yaml_line_before(lines, parent_end_1based, key_line_0)

            line_map[current_path] = LineRange(start=start_1based, end=end_1based)

        else:
            is_block_scalar = isinstance(value, ScalarString) and "\n" in str(value)

            if key_line_0 == val_line_0 and not is_block_scalar:
                line_map[current_path] = LineRange(start=start_1based, end=start_1based)
            else:
                if idx + 1 < len(keys):
                    next_key = keys[idx + 1]
                    next_key_line_0 = lc_data[next_key][0]
                    end_1based = _last_non_empty_yaml_line_before(lines, next_key_line_0, key_line_0)
                else:
                    end_1based = _last_non_empty_yaml_line_before(lines, parent_end_1based, key_line_0)

                line_map[current_path] = LineRange(start=start_1based, end=end_1based)
