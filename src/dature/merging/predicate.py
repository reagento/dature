from dataclasses import dataclass, fields, is_dataclass
from typing import TYPE_CHECKING, Any, get_type_hints

from dature.field_path import FieldPath, resolve_field_type, validate_field_path_owner
from dature.merging.strategy import FieldMergeStrategyEnum
from dature.protocols import DataclassInstance

if TYPE_CHECKING:
    from dature.types import FieldGroupTuple, FieldMergeCallable, FieldMergeMap


@dataclass(frozen=True, slots=True)
class ResolvedFieldGroup:
    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldMergeMaps:
    enum_map: dict[str, FieldMergeStrategyEnum]
    callable_map: "dict[str, FieldMergeCallable]"

    @property
    def callable_paths(self) -> frozenset[str]:
        return frozenset(self.callable_map.keys())


def extract_field_path(predicate: Any, schema: type[DataclassInstance] | None = None) -> str:  # noqa: ANN401
    if not isinstance(predicate, FieldPath):
        msg = f"Expected FieldPath, got {type(predicate).__name__}"
        raise TypeError(msg)
    if schema is not None:
        validate_field_path_owner(predicate, schema)
    return predicate.as_path()


def build_field_merge_map(
    field_merges: "FieldMergeMap | None",
    schema: type[DataclassInstance] | None = None,
) -> FieldMergeMaps:
    enum_map: dict[str, FieldMergeStrategyEnum] = {}
    callable_map: dict[str, FieldMergeCallable] = {}
    if not field_merges:
        return FieldMergeMaps(enum_map=enum_map, callable_map=callable_map)
    for predicate, strategy in field_merges.items():
        path = extract_field_path(predicate, schema)
        if isinstance(strategy, str):
            enum_map[path] = FieldMergeStrategyEnum(strategy)
        else:
            callable_map[path] = strategy
    return FieldMergeMaps(enum_map=enum_map, callable_map=callable_map)


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
