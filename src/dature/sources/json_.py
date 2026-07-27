import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from json.decoder import JSONArray, JSONObject, scanstring  # type: ignore[attr-defined]
from json.scanner import py_make_scanner  # type: ignore[attr-defined]
from typing import cast

from adaptix import loader
from adaptix.provider import Provider

from dature.coercion import (
    bytearray_from_string,
    date_from_string,
    datetime_from_string,
    float_from_string,
    time_from_string,
)
from dature.errors import LineRange
from dature.sources.base import FileSource
from dature.type_aliases import FILE_LIKE_TYPES, FileOrStream, JSONValue

_ScanOnce = Callable[[str, int], tuple[JSONValue, int]]


@dataclass(frozen=True, slots=True)
class _ExtractedKey:
    key: str | None
    position: int


@dataclass(kw_only=True, repr=False)
class JsonSource(FileSource):
    format_name: str = "json"

    def format_loaders(self) -> list[Provider]:
        return [
            loader(float, float_from_string),
            loader(date, date_from_string),
            loader(datetime, datetime_from_string),
            loader(time, time_from_string),
            loader(bytearray, bytearray_from_string),
        ]

    def _load_file(self, path: FileOrStream) -> JSONValue:
        if isinstance(path, FILE_LIKE_TYPES):
            return cast("JSONValue", json.load(path))
        with path.open(encoding=self.encoding) as file:
            return cast("JSONValue", json.load(file))

    def build_line_index(self, content: str) -> dict[tuple[str, ...], LineRange] | None:
        return _build_json_line_map(content)


def _build_json_line_map(content: str) -> dict[tuple[str, ...], LineRange]:
    line_map: dict[tuple[str, ...], LineRange] = {}
    path_stack: list[str] = []

    decoder = json.JSONDecoder()

    def _char_to_line(idx: int) -> int:
        return content.count("\n", 0, idx) + 1

    def _wrapping_parse_object(
        s_and_end: tuple[str, int],
        strict: bool,  # noqa: FBT001
        scan_once: _ScanOnce,
        object_hook: Callable[[JSONValue], JSONValue],
        object_pairs_hook: Callable[[JSONValue], JSONValue],
        memo: dict[str, str] | None = None,
    ) -> tuple[JSONValue, int]:
        def tracking_scan_once(s: str, idx: int) -> tuple["JSONValue", int]:
            extracted = _extract_json_key_before_value(s, idx)
            if extracted.key is not None:
                path_stack.append(extracted.key)

            obj, end = scan_once(s, idx)

            if extracted.key is not None:
                line_map[tuple(path_stack)] = LineRange(
                    start=_char_to_line(extracted.position),
                    end=_char_to_line(end - 1),
                )
                path_stack.pop()

            return obj, end

        return JSONObject(  # type: ignore[no-any-return]
            s_and_end,
            strict,
            tracking_scan_once,
            object_hook,
            object_pairs_hook,
            memo,
        )

    def _wrapping_parse_array(
        s_and_end: tuple[str, int],
        scan_once: _ScanOnce,
    ) -> tuple[list[JSONValue], int]:
        idx = 0

        def tracking_scan_once(s: str, pos: int) -> tuple["JSONValue", int]:
            nonlocal idx
            path_stack.append(str(idx))
            obj, end = scan_once(s, pos)
            path_stack.pop()
            idx += 1
            return obj, end

        return JSONArray(s_and_end, tracking_scan_once)  # type: ignore[no-any-return]

    decoder.parse_object = _wrapping_parse_object  # type: ignore[attr-defined]
    decoder.parse_array = _wrapping_parse_array  # type: ignore[attr-defined]
    decoder.scan_once = py_make_scanner(decoder)  # type: ignore[attr-defined]
    decoder.decode(content)
    return line_map


def _extract_json_key_before_value(s: str, val_start: int) -> _ExtractedKey:
    """Find JSON object key by scanning backwards from the value start position."""
    pos = val_start - 1
    while pos >= 0 and s[pos] in " \t\n\r:":
        pos -= 1

    if pos < 0 or s[pos] != '"':
        return _ExtractedKey(key=None, position=val_start)

    pos -= 1
    while pos >= 0:
        if s[pos] == '"':
            num_backslashes = 0
            check = pos - 1
            while check >= 0 and s[check] == "\\":
                num_backslashes += 1
                check -= 1
            if num_backslashes % 2 == 0:
                key, _ = scanstring(s, pos + 1, True)  # noqa: FBT003
                return _ExtractedKey(key=key, position=pos)
        pos -= 1

    return _ExtractedKey(key=None, position=val_start)
