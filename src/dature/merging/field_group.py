from dataclasses import dataclass
from typing import Any

from dature.errors import FieldGroupError, FieldGroupViolationError
from dature.merging.predicate import ResolvedFieldGroup
from dature.types import JSONValue

_SENTINEL = object()


@dataclass(frozen=True, slots=True)
class FieldGroupContext:
    source_reprs: tuple[str, ...]
    field_origins: dict[str, int]
    dataclass_name: str


def _get_nested_value(data: JSONValue, dot_path: str) -> Any:  # noqa: ANN401
    if not isinstance(data, dict):
        return _SENTINEL
    parts = dot_path.split(".")
    current: JSONValue = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return _SENTINEL
        current = current[part]
    return current


def validate_field_groups(
    *,
    base: JSONValue,
    source: JSONValue,
    field_group_paths: tuple[ResolvedFieldGroup, ...],
    source_index: int,
    ctx: FieldGroupContext,
) -> None:
    violations: list[FieldGroupViolationError] = []
    current_source_repr = ctx.source_reprs[source_index]

    for group in field_group_paths:
        changed: list[str] = []
        changed_sources: list[str] = []
        unchanged: list[str] = []
        unchanged_sources: list[str] = []

        for path in group.paths:
            source_val = _get_nested_value(source, path)
            if source_val is _SENTINEL:
                unchanged.append(path)
                origin_idx = ctx.field_origins.get(path)
                if origin_idx is not None:
                    unchanged_sources.append(ctx.source_reprs[origin_idx])
                else:
                    unchanged_sources.append("none")
                continue
            base_val = _get_nested_value(base, path)
            if source_val == base_val:
                unchanged.append(path)
                origin_idx = ctx.field_origins.get(path)
                if origin_idx is not None:
                    unchanged_sources.append(ctx.source_reprs[origin_idx])
                else:
                    unchanged_sources.append(current_source_repr)
            else:
                changed.append(path)
                changed_sources.append(current_source_repr)

        if changed and unchanged:
            violations.append(
                FieldGroupViolationError(
                    group_fields=group.paths,
                    changed_fields=tuple(changed),
                    unchanged_fields=tuple(unchanged),
                    changed_sources=tuple(changed_sources),
                    unchanged_sources=tuple(unchanged_sources),
                    source_index=source_index,
                ),
            )

    if violations:
        raise FieldGroupError(ctx.dataclass_name, violations)
