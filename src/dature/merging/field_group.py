from dataclasses import dataclass

from dature.errors import FieldGroupError, FieldGroupViolationError
from dature.merging.deep_merge import deep_merge_last_wins
from dature.merging.predicate import ResolvedFieldGroup
from dature.nested_dict import ABSENT, collect_leaf_paths, get_nested_value
from dature.type_aliases import JSONValue


@dataclass(frozen=True, slots=True)
class FieldGroupContext:
    source_reprs: tuple[str, ...]
    field_origins: dict[str, int]
    dataclass_name: str


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
            source_val = get_nested_value(source, path)
            if source_val is ABSENT:
                unchanged.append(path)
                origin_idx = ctx.field_origins.get(path)
                if origin_idx is not None:
                    unchanged_sources.append(ctx.source_reprs[origin_idx])
                else:
                    unchanged_sources.append("none")
                continue
            base_val = get_nested_value(base, path)
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


def validate_all_field_groups(
    *,
    raw_dicts: list[JSONValue],
    field_group_paths: tuple[ResolvedFieldGroup, ...],
    dataclass_name: str,
    source_reprs: tuple[str, ...],
) -> None:
    """Run field-group consistency validation across all sources in *raw_dicts*.

    Simulates the merge step-by-step so each source is validated against the
    cumulative state that precedes it — the same order the merge strategy would apply.
    Raises ``FieldGroupError`` on the first violation found.
    """
    merged: JSONValue = {}
    field_origins: dict[str, int] = {}
    ctx = FieldGroupContext(
        source_reprs=source_reprs,
        field_origins=field_origins,
        dataclass_name=dataclass_name,
    )
    for step_index, raw in enumerate(raw_dicts):
        validate_field_groups(
            base=merged,
            source=raw,
            field_group_paths=field_group_paths,
            source_index=step_index,
            ctx=ctx,
        )
        for leaf_path in collect_leaf_paths(raw):
            field_origins[leaf_path] = step_index
        merged = deep_merge_last_wins(merged, raw)
