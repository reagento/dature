from dature.errors import MergeConflictError, MergeConflictFieldError, SourceLocation
from dature.errors.location import resolve_source_location
from dature.loading.source_loading import SourceContext
from dature.types import JSONValue

_MIN_CONFLICT_SOURCES = 2


def deep_merge_last_wins(base: JSONValue, override: JSONValue) -> JSONValue:
    if isinstance(base, dict) and isinstance(override, dict):
        result = dict(base)
        for key, value in override.items():
            if key in result:
                result[key] = deep_merge_last_wins(result[key], value)
            else:
                result[key] = value
        return result
    return override


def deep_merge_first_wins(base: JSONValue, override: JSONValue) -> JSONValue:
    if isinstance(base, dict) and isinstance(override, dict):
        result = dict(base)
        for key, value in override.items():
            if key in result:
                result[key] = deep_merge_first_wins(result[key], value)
            else:
                result[key] = value
        return result
    return base


def _collect_conflicts(
    dicts: list[JSONValue],
    source_contexts: list[SourceContext],
    path: list[str],
    conflicts: list[tuple[list[str], list[tuple[int, JSONValue]]]],
    field_merge_paths: frozenset[str] | None = None,
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
        if field_merge_paths is not None and field_path in field_merge_paths:
            continue

        values = [v for _, v in sources]

        nested_dicts = [v for v in values if isinstance(v, dict)]
        if len(nested_dicts) == len(sources):
            _collect_conflicts(
                values,
                [source_contexts[i] for i, _ in sources],
                [*path, key],
                conflicts,
                field_merge_paths=field_merge_paths,
            )
            continue

        if all(v == values[0] for v in values[1:]):
            continue

        conflicts.append(([*path, key], sources))


def raise_on_conflict(
    dicts: list[JSONValue],
    source_ctxs: list[SourceContext],
    dataclass_name: str,
    field_merge_paths: frozenset[str] | None = None,
) -> None:
    conflicts: list[tuple[list[str], list[tuple[int, JSONValue]]]] = []
    _collect_conflicts(
        dicts,
        source_ctxs,
        [],
        conflicts,
        field_merge_paths=field_merge_paths,
    )

    if not conflicts:
        return

    conflict_errors: list[MergeConflictFieldError] = []
    for field_path, sources in conflicts:
        locations: list[SourceLocation] = []
        for source_idx, _ in sources:
            source_ctx = source_ctxs[source_idx]
            locs = resolve_source_location(field_path, source_ctx.error_ctx, source_ctx.file_content)
            locations.extend(locs)
        conflict_errors.append(
            MergeConflictFieldError(
                field_path=field_path,
                message="Conflicting values in multiple sources",
                locations=locations,
            ),
        )

    raise MergeConflictError(dataclass_name, conflict_errors)
