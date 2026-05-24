Internal: merged `path_finders/` module into the corresponding `sources/` files. No public API change.

**What changed:**

- `src/dature/path_finders/` removed entirely (was internal, never exported).
- `src/dature/_descriptors.py` (`classproperty`) removed — no longer needed.
- `Source.path_finder_class` class variable removed.
- New `Source._build_line_index(content: str) -> dict[tuple[str, ...], LineRange] | None` method added.
  Default returns `None` (no diagnostics). Format sources override it to return a line map.
- Line-lookup logic for yaml, toml, json, json5, ini now lives in the same file as the corresponding `Source` class (e.g. `sources/yaml_.py` contains `_build_yaml_line_map` and `_walk_yaml_mapping`).
- `_find_parent_line_range` in `Source` updated to accept a dict instead of a `PathFinder` instance.
- Tests from `tests/path_finders/` moved to `tests/sources/test_<fmt>_line_index.py`.

**For custom Source subclasses** (private API): if you previously set `path_finder_class` on a custom source, override `_build_line_index` instead. Return a `dict[tuple[str, ...], LineRange]` mapping dotted key paths to line ranges, or `None` to disable diagnostics.
