from json5.model import Identifier, JSONArray, JSONObject, String, Value
from json5.parser import parse_source

from dature.errors.exceptions import LineRange
from dature.path_finders.base import PathFinder


class Json5PathFinder(PathFinder):
    def __init__(self, content: str) -> None:
        self._line_map = _build_json5_line_map(content)

    def find_line_range(self, target_path: list[str]) -> LineRange | None:
        return self._line_map.get(tuple(target_path))


def _build_json5_line_map(content: str) -> dict[tuple[str, ...], LineRange]:
    model = parse_source(content)
    line_map: dict[tuple[str, ...], LineRange] = {}
    _walk(model.value, (), line_map)
    return line_map


def _walk(node: Value, parent_path: tuple[str, ...], line_map: dict[tuple[str, ...], LineRange]) -> None:
    if isinstance(node, JSONObject):
        _walk_object(node, parent_path, line_map)
    elif isinstance(node, JSONArray):
        _walk_array(node, parent_path, line_map)


def _walk_object(
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
        _walk(val_node, current_path, line_map)


def _walk_array(
    arr: JSONArray,
    parent_path: tuple[str, ...],
    line_map: dict[tuple[str, ...], LineRange],
) -> None:
    for index, val_node in enumerate(arr.values):
        current_path = (*parent_path, str(index))
        _walk(val_node, current_path, line_map)
