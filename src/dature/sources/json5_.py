import io
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import TextIO, cast

from adaptix import loader
from adaptix.provider import Provider

from dature._deps import require_dep
from dature.errors import LineRange
from dature.loaders import (
    bytearray_from_string,
    date_from_string,
    datetime_from_string,
    float_from_string,
    time_from_string,
)
from dature.loaders.json5_ import str_from_json_identifier
from dature.sources.base import FileSource
from dature.types import BINARY_IO_TYPES, TEXT_IO_TYPES, FileOrStream, JSONValue

try:
    from json5.model import Identifier, JSONArray, JSONObject, String, Value
except ImportError:  # pragma: no cover
    Identifier = object  # type: ignore[misc, assignment]
    JSONArray = object  # type: ignore[misc, assignment]
    JSONObject = object  # type: ignore[misc, assignment]
    String = object  # type: ignore[misc, assignment]
    Value = object  # type: ignore[misc, assignment]


@dataclass(kw_only=True, repr=False)
class Json5Source(FileSource):
    format_name = "json5"

    def additional_loaders(self) -> list[Provider]:
        return [
            loader(str, str_from_json_identifier),
            loader(float, float_from_string),
            loader(date, date_from_string),
            loader(datetime, datetime_from_string),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]

    def _load_file(self, path: FileOrStream) -> JSONValue:
        require_dep("json5", "json5")
        import json5  # noqa: PLC0415

        if isinstance(path, TEXT_IO_TYPES):
            return cast("JSONValue", json5.load(cast("TextIO", path)))
        if isinstance(path, BINARY_IO_TYPES):
            return cast(
                "JSONValue", json5.load(io.TextIOWrapper(cast("io.BufferedReader", path), encoding=self.encoding))
            )
        with path.open(encoding=self.encoding) as file:
            return cast("JSONValue", json5.load(file))

    def _build_line_index(self, content: str) -> dict[tuple[str, ...], LineRange] | None:
        return _build_json5_line_map(content)


def _build_json5_line_map(content: str) -> dict[tuple[str, ...], LineRange]:
    require_dep("json5", "json5")
    from json5.parser import parse_source  # noqa: PLC0415

    model = parse_source(content)
    line_map: dict[tuple[str, ...], LineRange] = {}
    _walk_json5(model.value, (), line_map)
    return line_map


def _walk_json5(node: Value, parent_path: tuple[str, ...], line_map: dict[tuple[str, ...], LineRange]) -> None:
    if isinstance(node, JSONObject):
        _walk_json5_object(node, parent_path, line_map)
    elif isinstance(node, JSONArray):
        _walk_json5_array(node, parent_path, line_map)


def _walk_json5_object(
    obj: JSONObject,
    parent_path: tuple[str, ...],
    line_map: dict[tuple[str, ...], LineRange],
) -> None:
    for kvp in obj.key_value_pairs:
        key_node = kvp[0]
        val_node = kvp[1]

        if isinstance(key_node, Identifier):
            key_name = key_node.name
        elif isinstance(key_node, String):
            key_name = key_node.characters
        else:
            continue

        current_path = (*parent_path, key_name)

        start = key_node.lineno
        end = val_node.end_lineno
        if start is None or end is None:
            continue

        line_map[current_path] = LineRange(start=start, end=end)
        _walk_json5(val_node, current_path, line_map)


def _walk_json5_array(
    arr: JSONArray,
    parent_path: tuple[str, ...],
    line_map: dict[tuple[str, ...], LineRange],
) -> None:
    for index, val_node in enumerate(arr.values):
        current_path = (*parent_path, str(index))
        _walk_json5(val_node, current_path, line_map)
