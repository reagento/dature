from dataclasses import dataclass, is_dataclass
from functools import partial
from typing import get_type_hints

from adaptix import Chain, Provider, loader

from dature.field_path import FieldPath
from dature.protocols import DataclassInstance
from dature.type_aliases import FieldMapping, JSONValue
from dature.type_utils import find_nested_dataclasses


@dataclass(frozen=True, slots=True)
class AliasEntry:
    field_name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CrossLevelEntry:
    dest_path: tuple[str, ...]
    field_name: str
    aliases: tuple[str, ...]


type AliasMapEntry = AliasEntry | CrossLevelEntry


def resolve_nested_owner(
    owner: type[DataclassInstance],
    parts: tuple[str, ...],
) -> type[DataclassInstance]:
    """Walk type hints from owner through intermediate parts to find the leaf owner type."""
    current: type = owner
    for part in parts:
        hints = get_type_hints(current)
        if part not in hints:
            msg = f"Type '{current.__name__}' has no field '{part}'"
            raise TypeError(msg)
        current = hints[part]
        if not is_dataclass(current):
            msg = f"Intermediate field '{part}' of type '{current}' is not a dataclass"
            raise TypeError(msg)
    return current


def _classify_alias(
    alias: str,
    field_nesting: tuple[str, ...],
) -> str | None:
    """Return stripped alias for same-level, or None for cross-level."""
    if "." not in alias:
        return None

    segments = alias.split(".")
    prefix = tuple(segments[:-1])
    if prefix == field_nesting:
        return segments[-1]
    return None


def _add_entry(
    alias_map: dict[type[DataclassInstance] | str, list[AliasMapEntry]],
    owner: type[DataclassInstance] | str,
    entry: AliasMapEntry,
) -> None:
    if owner not in alias_map:
        alias_map[owner] = []
    alias_map[owner].append(entry)


def _process_nested_field_path(
    alias_map: dict[type[DataclassInstance] | str, list[AliasMapEntry]],
    field_path: FieldPath,
    alias_tuple: tuple[str, ...],
) -> None:
    if isinstance(field_path.owner, str):
        msg = (
            f"Nested FieldPath with string owner '{field_path.owner}' "
            f"is not supported — cannot resolve intermediate types"
        )
        raise TypeError(msg)

    intermediate_parts = field_path.parts[:-1]
    resolved_owner = resolve_nested_owner(field_path.owner, intermediate_parts)
    field_name = field_path.parts[-1]

    same_level_aliases: list[str] = []
    cross_level_aliases: list[str] = []

    for alias in alias_tuple:
        stripped = _classify_alias(alias, intermediate_parts)
        if stripped is not None:
            same_level_aliases.append(stripped)
        else:
            same_level_aliases.append(alias)
            cross_level_aliases.append(alias)

    if same_level_aliases:
        _add_entry(
            alias_map,
            resolved_owner,
            AliasEntry(field_name=field_name, aliases=tuple(same_level_aliases)),
        )

    if cross_level_aliases:
        _add_entry(
            alias_map,
            field_path.owner,
            CrossLevelEntry(
                dest_path=intermediate_parts,
                field_name=field_name,
                aliases=tuple(cross_level_aliases),
            ),
        )


def _build_alias_map(
    field_mapping: FieldMapping,
) -> dict[type[DataclassInstance] | str, list[AliasMapEntry]]:
    alias_map: dict[type[DataclassInstance] | str, list[AliasMapEntry]] = {}

    for field_path_key, aliases in field_mapping.items():
        if not isinstance(field_path_key, FieldPath):
            msg = f"field_mapping key must be a FieldPath, got {type(field_path_key).__name__}"
            raise TypeError(msg)

        alias_tuple: tuple[str, ...]
        if isinstance(aliases, str):
            alias_tuple = (aliases,)
        else:
            alias_tuple = aliases

        if len(field_path_key.parts) == 0:
            msg = "FieldPath must contain at least one field name"
            raise ValueError(msg)

        if len(field_path_key.parts) > 1:
            _process_nested_field_path(alias_map, field_path_key, alias_tuple)
            continue

        _add_entry(
            alias_map,
            field_path_key.owner,
            AliasEntry(field_name=field_path_key.parts[-1], aliases=alias_tuple),
        )

    return alias_map


def _navigate_to(data: dict[str, JSONValue], path: tuple[str, ...]) -> dict[str, JSONValue] | None:
    current = data
    for key in path:
        value = current.get(key)
        if not isinstance(value, dict):
            return None
        current = value
    return current


def _apply_alias_entry(result: dict[str, JSONValue], entry: AliasEntry) -> None:
    if entry.field_name in result:
        return
    for alias in entry.aliases:
        if alias in result:
            result[entry.field_name] = result.pop(alias)
            return


def _apply_cross_level_entry(result: dict[str, JSONValue], entry: CrossLevelEntry) -> None:
    dest = _navigate_to(result, entry.dest_path)
    if dest is None:
        return
    if entry.field_name in dest:
        return
    for alias in entry.aliases:
        if alias in result:
            dest[entry.field_name] = result.pop(alias)
            return


def _transform_dict(data: JSONValue, entries: list[AliasMapEntry]) -> JSONValue:
    if not isinstance(data, dict):
        return data

    result = dict(data)
    for entry in entries:
        if isinstance(entry, AliasEntry):
            _apply_alias_entry(result, entry)
        else:
            _apply_cross_level_entry(result, entry)

    return result


def _collect_reachable_dataclasses(schema: type[DataclassInstance]) -> dict[str, type]:
    """Map ``__name__`` to type for *schema* and every dataclass reachable from its fields."""
    by_name: dict[str, type] = {}
    queue: list[type] = [schema]
    while queue:
        current = queue.pop()
        if current.__name__ in by_name:
            continue
        by_name[current.__name__] = current
        queue.extend(
            nested
            for field_type in get_type_hints(current).values()
            for nested in find_nested_dataclasses(field_type)
            if nested.__name__ not in by_name
        )
    return by_name


def build_alias_loaders(
    field_mapping: FieldMapping,
    schema: type[DataclassInstance] | None,
) -> list[Provider]:
    """Build public ``loader(owner, transform, Chain.FIRST)`` providers from *field_mapping*.

    Each owner dataclass gets one loader that rewrites raw-dict keys (alias renames and
    cross-level moves) before the model loader runs. String owners are resolved to their
    type by name against *schema* and its reachable dataclasses; a type owner takes
    precedence over a string owner naming the same type.
    """
    alias_map = _build_alias_map(field_mapping)

    resolved: dict[type, list[AliasMapEntry]] = {}
    string_keyed: list[tuple[str, list[AliasMapEntry]]] = []
    for owner, entries in alias_map.items():
        if isinstance(owner, type):
            resolved[owner] = entries
        else:
            string_keyed.append((owner, entries))

    if string_keyed and schema is not None:
        by_name = _collect_reachable_dataclasses(schema)
        for name, entries in string_keyed:
            owner_type = by_name.get(name)
            if owner_type is not None and owner_type not in resolved:
                resolved[owner_type] = entries

    return [
        loader(owner_type, partial(_transform_dict, entries=entries), Chain.FIRST)
        for owner_type, entries in resolved.items()
    ]
