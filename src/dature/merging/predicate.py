from dataclasses import dataclass, fields, is_dataclass
from typing import TYPE_CHECKING, get_type_hints

from dature.field_path import FieldPath, extract_field_path, resolve_field_type
from dature.protocols import DataclassInstance
from dature.strategies.field import FieldMergeStrategy, resolve_field_strategy

if TYPE_CHECKING:
    from dature.types import FieldGroupTuple, FieldMergeMap


@dataclass(frozen=True, slots=True)
class ResolvedFieldGroup:
    paths: tuple[str, ...]


def build_field_merge_map(
    field_merges: "FieldMergeMap | None",
    schema: type[DataclassInstance] | None = None,
    *,
    dataclass_name: str = "<unknown>",
) -> "dict[str, FieldMergeStrategy]":
    if not field_merges:
        return {}

    result: dict[str, FieldMergeStrategy] = {}
    for predicate, strategy in field_merges.items():
        path = extract_field_path(predicate, schema)
        if isinstance(strategy, str):
            result[path] = resolve_field_strategy(strategy, dataclass_name=dataclass_name)
        elif callable(strategy):
            result[path] = strategy
        else:
            msg = f"Invalid field merge strategy for {path!r}: expected name, callable, or FieldMergeStrategy instance"
            raise TypeError(msg)
    return result


def _expand_dataclass_fields(prefix: str, dc_type: type) -> list[str]:
    result: list[str] = []
    hints = get_type_hints(dc_type)
    for f in fields(dc_type):
        child_path = f"{prefix}.{f.name}" if prefix else f.name
        child_type = hints.get(f.name)
        if child_type is not None and is_dataclass(child_type):
            result.extend(_expand_dataclass_fields(child_path, child_type))
        else:
            result.append(child_path)
    return result


def build_field_group_paths(
    field_groups: "tuple[FieldGroupTuple, ...]",
    schema: type[DataclassInstance],
) -> tuple[ResolvedFieldGroup, ...]:
    resolved: list[ResolvedFieldGroup] = []
    for group in field_groups:
        paths: list[str] = []
        for field in group:
            path = extract_field_path(field, schema)
            if isinstance(field, FieldPath) and isinstance(field.owner, type):
                resolved_type = resolve_field_type(field.owner, field.parts)
            else:
                resolved_type = resolve_field_type(schema, tuple(path.split(".")))
            if resolved_type is not None:
                paths.extend(_expand_dataclass_fields(path, resolved_type))
            else:
                paths.append(path)
        resolved.append(ResolvedFieldGroup(paths=tuple(paths)))
    return tuple(resolved)
