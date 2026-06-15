from collections.abc import Callable, Sequence
from dataclasses import dataclass, is_dataclass
from typing import cast

from adaptix import Loader, Mediator, Provider

from dature._adaptix_compat import AlwaysTrueRequestChecker, LoaderRequest, RequestHandlerRegisterRecord
from dature.field_path import Absolute, FieldPath, resolve_nested_owner
from dature.protocols import DataclassInstance
from dature.type_aliases import FieldMapping, JSONValue


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
        if isinstance(alias, Absolute):
            # Absolute aliases are resolved at the source level; skip them here.
            continue
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

        # Drop Absolute aliases — they are resolved at the source level (before prefix
        # navigation / prefix filter), so the AliasProvider must not apply them again.
        relative_aliases = tuple(a for a in alias_tuple if not isinstance(a, Absolute))
        if not relative_aliases:
            continue

        if len(field_path_key.parts) > 1:
            _process_nested_field_path(alias_map, field_path_key, relative_aliases)
            continue

        _add_entry(
            alias_map,
            field_path_key.owner,
            AliasEntry(field_name=field_path_key.parts[-1], aliases=relative_aliases),
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


def _get_entries_for_type(
    alias_map: dict[type[DataclassInstance] | str, list[AliasMapEntry]],
    target_type: type[DataclassInstance],
) -> list[AliasMapEntry] | None:
    entries = alias_map.get(target_type)
    if entries is not None:
        return entries

    for owner, owner_entries in alias_map.items():
        if isinstance(owner, str) and owner == target_type.__name__:
            return owner_entries

    return None


class AliasProvider(Provider):
    def __init__(self, field_mapping: FieldMapping) -> None:
        self._alias_map = _build_alias_map(field_mapping)

    def _wrap_handler(
        self,
        mediator: Mediator[Loader[JSONValue]],
        request: LoaderRequest,
    ) -> Callable[[JSONValue], JSONValue]:
        next_handler = mediator.provide_from_next()
        target_type = request.last_loc.type

        if not is_dataclass(target_type):
            return next_handler

        entries = _get_entries_for_type(
            self._alias_map,
            cast("type[DataclassInstance]", target_type),
        )
        if entries is None:
            return next_handler

        def aliased_handler(data: JSONValue) -> JSONValue:
            transformed = _transform_dict(data, entries)
            return next_handler(transformed)

        return aliased_handler

    def get_request_handlers(self) -> Sequence[RequestHandlerRegisterRecord]:
        return [(LoaderRequest, AlwaysTrueRequestChecker(), self._wrap_handler)]
