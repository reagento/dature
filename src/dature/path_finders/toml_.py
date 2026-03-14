from typing import TYPE_CHECKING, cast

import toml_rs
from toml_rs._lib import TomlVersion

from dature.errors.exceptions import LineRange
from dature.path_finders.base import PathFinder

if TYPE_CHECKING:
    from toml_rs._toml_rs import KeyMeta


class TomlPathFinder(PathFinder):
    def __init__(self, content: str, *, toml_version: TomlVersion) -> None:
        self._line_map = _build_toml_line_map(content, toml_version)

    def find_line_range(self, target_path: list[str]) -> LineRange | None:
        return self._line_map.get(tuple(target_path))


class Toml10PathFinder(TomlPathFinder):
    def __init__(self, content: str) -> None:
        super().__init__(content, toml_version="1.0.0")


class Toml11PathFinder(TomlPathFinder):
    def __init__(self, content: str) -> None:
        super().__init__(content, toml_version="1.1.0")


def _build_toml_line_map(content: str, toml_version: TomlVersion) -> dict[tuple[str, ...], LineRange]:
    doc = toml_rs.load_with_metadata(content, toml_version=toml_version)
    line_map: dict[tuple[str, ...], LineRange] = {}
    _walk_nodes(doc.meta["nodes"], (), line_map)
    return line_map


def _walk_nodes(
    nodes: "dict[str, KeyMeta]",
    prefix: tuple[str, ...],
    line_map: dict[tuple[str, ...], LineRange],
) -> None:
    for name, node in nodes.items():
        if not isinstance(node, dict):
            continue
        path = (*prefix, name)
        if "key" not in node:
            # section header (e.g. [database]) — recurse into children
            _walk_nodes(cast("dict[str, KeyMeta]", node), path, line_map)
            continue
        _process_leaf_or_inline_table(node, path, line_map)


def _process_leaf_or_inline_table(
    node: "KeyMeta",
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
        line_map[path] = LineRange(start=start, end=end)
        if isinstance(value, dict):
            # inline table — recurse into children
            _walk_nodes(cast("dict[str, KeyMeta]", value), path, line_map)
        return

    if isinstance(value, list):
        # array of tables ([[section]]) — recurse into each element with index
        for idx, element in enumerate(value):
            if not isinstance(element, dict):
                continue
            inner = element.get("value")
            if isinstance(inner, dict):
                indexed_path = (*path, str(idx))
                _walk_nodes(cast("dict[str, KeyMeta]", inner), indexed_path, line_map)
