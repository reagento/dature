from dataclasses import dataclass

from dature.errors.exceptions import MergeConflictError, MergeConflictFieldError, SourceLocation
from dature.errors.location import resolve_source_location
from dature.loading.source_loading import SourceContext
from dature.metadata import FieldMergeStrategy, MergeStrategy
from dature.types import JSONValue

_MIN_CONFLICT_SOURCES = 2


def _deduplicate_list(items: list[JSONValue]) -> list[JSONValue]:
    seen: list[JSONValue] = []
    for item in items:
        found = False
        for s in seen:
            if s == item:
                found = True
                break
        if not found:
            seen.append(item)
    return seen


@dataclass(frozen=True, slots=True)
class ListPair:
    base: list[JSONValue]
    override: list[JSONValue]


def _ensure_both_lists(
    base: JSONValue,
    override: JSONValue,
    strategy_name: str,
) -> ListPair:
    if not isinstance(base, list) or not isinstance(override, list):
        base_type = type(base).__name__
        override_type = type(override).__name__
        msg = f"{strategy_name} strategy requires both values to be lists, got {base_type} and {override_type}"
        raise TypeError(msg)
    return ListPair(base=base, override=override)


def _apply_list_merge(
    base: JSONValue,
    override: JSONValue,
    strategy: FieldMergeStrategy,
) -> list[JSONValue]:
    if strategy == FieldMergeStrategy.APPEND:
        pair = _ensure_both_lists(base, override, "APPEND")
        return list(pair.base) + list(pair.override)

    if strategy == FieldMergeStrategy.APPEND_UNIQUE:
        pair = _ensure_both_lists(base, override, "APPEND_UNIQUE")
        return _deduplicate_list(list(pair.base) + list(pair.override))

    if strategy == FieldMergeStrategy.PREPEND:
        pair = _ensure_both_lists(base, override, "PREPEND")
        return list(pair.override) + list(pair.base)

    # PREPEND_UNIQUE
    pair = _ensure_both_lists(base, override, "PREPEND_UNIQUE")
    return _deduplicate_list(list(pair.override) + list(pair.base))


def apply_field_merge(
    base: JSONValue,
    override: JSONValue,
    strategy: FieldMergeStrategy,
) -> JSONValue:
    if strategy == FieldMergeStrategy.FIRST_WINS:
        return base

    if strategy == FieldMergeStrategy.LAST_WINS:
        return override

    return _apply_list_merge(base, override, strategy)


def deep_merge_last_wins(
    base: JSONValue,
    override: JSONValue,
    *,
    field_merge_map: dict[str, FieldMergeStrategy] | None = None,
    _path: str = "",
) -> JSONValue:
    if field_merge_map is not None and _path in field_merge_map:
        return apply_field_merge(base, override, field_merge_map[_path])

    if isinstance(base, dict) and isinstance(override, dict):
        result = dict(base)
        for key, value in override.items():
            child_path = f"{_path}.{key}" if _path else key
            if key in result:
                result[key] = deep_merge_last_wins(
                    result[key],
                    value,
                    field_merge_map=field_merge_map,
                    _path=child_path,
                )
            else:
                result[key] = value
        return result
    return override


def deep_merge_first_wins(
    base: JSONValue,
    override: JSONValue,
    *,
    field_merge_map: dict[str, FieldMergeStrategy] | None = None,
    _path: str = "",
) -> JSONValue:
    if field_merge_map is not None and _path in field_merge_map:
        return apply_field_merge(base, override, field_merge_map[_path])

    if isinstance(base, dict) and isinstance(override, dict):
        result = dict(base)
        for key, value in override.items():
            child_path = f"{_path}.{key}" if _path else key
            if key in result:
                result[key] = deep_merge_first_wins(
                    result[key],
                    value,
                    field_merge_map=field_merge_map,
                    _path=child_path,
                )
            else:
                result[key] = value
        return result
    return base


def _collect_conflicts(
    dicts: list[JSONValue],
    source_contexts: list[SourceContext],
    path: list[str],
    conflicts: list[tuple[list[str], list[tuple[int, JSONValue]]]],
    field_merge_map: dict[str, FieldMergeStrategy] | None = None,
    callable_merge_paths: frozenset[str] | None = None,
) -> None:
    key_sources: dict[str, list[tuple[int, JSONValue]]] = {}

    for i, d in enumerate(dicts):
        if not isinstance(d, dict):
            continue
        for key, value in d.items():
            if key not in key_sources:
                key_sources[key] = []
            key_sources[key].append((i, value))

    for key, sources in key_sources.items():
        if len(sources) < _MIN_CONFLICT_SOURCES:
            continue

        field_path = ".".join([*path, key])
        has_enum_strategy = field_merge_map is not None and field_path in field_merge_map
        has_callable_strategy = callable_merge_paths is not None and field_path in callable_merge_paths
        if has_enum_strategy or has_callable_strategy:
            continue

        values = [v for _, v in sources]

        nested_dicts = [v for v in values if isinstance(v, dict)]
        if len(nested_dicts) == len(sources):
            _collect_conflicts(
                values,
                [source_contexts[i] for i, _ in sources],
                [*path, key],
                conflicts,
                field_merge_map=field_merge_map,
                callable_merge_paths=callable_merge_paths,
            )
            continue

        if all(v == values[0] for v in values[1:]):
            continue

        conflicts.append(([*path, key], sources))


def raise_on_conflict(
    dicts: list[JSONValue],
    source_ctxs: list[SourceContext],
    dataclass_name: str,
    field_merge_map: dict[str, FieldMergeStrategy] | None = None,
    callable_merge_paths: frozenset[str] | None = None,
) -> None:
    conflicts: list[tuple[list[str], list[tuple[int, JSONValue]]]] = []
    _collect_conflicts(
        dicts,
        source_ctxs,
        [],
        conflicts,
        field_merge_map=field_merge_map,
        callable_merge_paths=callable_merge_paths,
    )

    if not conflicts:
        return

    conflict_errors: list[MergeConflictFieldError] = []
    for field_path, sources in conflicts:
        locations: list[SourceLocation] = []
        for source_idx, _ in sources:
            source_ctx = source_ctxs[source_idx]
            loc = resolve_source_location(field_path, source_ctx.error_ctx, source_ctx.file_content)
            locations.append(loc)
        conflict_errors.append(
            MergeConflictFieldError(
                field_path=field_path,
                message="Conflicting values in multiple sources",
                locations=locations,
            ),
        )

    raise MergeConflictError(dataclass_name, conflict_errors)


def deep_merge(
    base: JSONValue,
    override: JSONValue,
    *,
    strategy: MergeStrategy,
    field_merge_map: dict[str, FieldMergeStrategy] | None = None,
) -> JSONValue:
    if strategy == MergeStrategy.LAST_WINS:
        return deep_merge_last_wins(base, override, field_merge_map=field_merge_map)
    if strategy == MergeStrategy.FIRST_WINS:
        return deep_merge_first_wins(base, override, field_merge_map=field_merge_map)
    msg = "Use merge_sources for RAISE_ON_CONFLICT strategy"
    raise ValueError(msg)
