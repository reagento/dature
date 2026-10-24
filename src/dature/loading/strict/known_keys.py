"""Schema → tree of keys known to strict mode.

Mirrors ``masking/detection.py``'s ``_walk_dataclass_fields``: a recursive walk of
dataclass fields, drilling into nested dataclasses directly, and into
``list``/``dict``/``tuple`` containers one level to find an element dataclass. A field
whose type is not itself a dataclass and has no such element (``dict[str, Any]``,
``list[str]``, ``Any``) is a known key with opaque, unscanned contents.

Aliases are resolved by *owning dataclass type*, not by string path — this matches
``AliasProvider``'s real lookup key (``_get_entries_for_type`` in
``providers/alias.py``), which applies regardless of where that dataclass
type is nested in the schema.
"""

import logging
import types
from dataclasses import dataclass, fields, is_dataclass
from functools import lru_cache
from typing import Annotated, Union, cast, get_args, get_origin, get_type_hints

from dature.naming import canonical_name
from dature.protocols import DataclassInstance
from dature.providers.alias import build_alias_map
from dature.type_aliases import FieldMapping, TypeAnnotation
from dature.type_utils import find_nested_dataclasses

logger = logging.getLogger("dature")

_PAIR_ARITY = 2  # tuple[X, ...] / dict[K, V] generic arg count


@dataclass(frozen=True, slots=True)
class ObjectNode:
    """A dataclass: the set of keys it accepts is known."""

    keys: frozenset[str]
    """Canonicalized (``canonical_name``) field names."""
    children: "dict[str, Node]"
    """Canonical field name → node describing that field's own nested shape, for fields
    that are themselves a dataclass or a container of one."""
    dc_type: type[DataclassInstance]
    """The dataclass this node was built from — used to look up aliases by owner type."""


@dataclass(frozen=True, slots=True)
class ElementsNode:
    """A ``list``/``dict``/``tuple`` of a dataclass: element keys are unconstrained data,
    every element is described by the same node."""

    element: "Node"


type Node = ObjectNode | ElementsNode


def _strip_annotated(field_type: TypeAnnotation) -> TypeAnnotation:
    while get_origin(field_type) is Annotated:
        field_type = get_args(field_type)[0]
    return field_type


def _element_type(field_type: TypeAnnotation) -> TypeAnnotation | None:
    """Return the container's element type for ``list``/``dict``/``tuple[X, ...]`` generics."""
    origin = get_origin(field_type)
    if origin in (list, set, frozenset):
        args = get_args(field_type)
        return cast("TypeAnnotation", args[0]) if args else None
    if origin is tuple:
        args = get_args(field_type)
        if len(args) == _PAIR_ARITY and args[1] is Ellipsis:  # tuple[X, ...] — uniform element type
            return cast("TypeAnnotation", args[0])
        return None
    if origin is dict:
        args = get_args(field_type)
        if len(args) == _PAIR_ARITY:
            return cast("TypeAnnotation", args[1])
    return None


def _node_for_field_type(
    field_type: TypeAnnotation, memo: "dict[type[DataclassInstance], ObjectNode]"
) -> "Node | None":
    """Build the node describing *field_type*'s own nested shape, if it has one.

    ``find_nested_dataclasses`` (``type_utils.py``) already strips ``Annotated``/``Union``
    recursively, so it is reused here for both cases below — the two are kept separate
    because a `Union` member (e.g. `Db | None`) sits at the *same* path as the field
    itself, while a container element (`list[Db]`) adds an index/key path segment.
    """
    stripped = _strip_annotated(field_type)
    if is_dataclass(stripped) and isinstance(stripped, type):
        return _build_object_node(stripped, memo)

    if get_origin(stripped) is Union or isinstance(stripped, types.UnionType):
        for candidate in find_nested_dataclasses(stripped):
            return _build_object_node(candidate, memo)
        return None

    elem = _element_type(stripped)
    if elem is not None:
        for candidate in find_nested_dataclasses(elem):
            return ElementsNode(element=_build_object_node(candidate, memo))

    return None


def _build_object_node(
    dataclass_type: "type[DataclassInstance]", memo: "dict[type[DataclassInstance], ObjectNode]"
) -> ObjectNode:
    """Build (or reuse) the node for *dataclass_type*, guarding against cycles/diamonds.

    A self-referential or mutually-recursive schema (``child: "N | None"``) would recurse
    unboundedly without this: *memo* is populated with the node *before* its children are
    filled in, so a cycle back to a type already being built returns the same (still being
    populated, but already-registered) node instead of recursing again.
    """
    existing = memo.get(dataclass_type)
    if existing is not None:
        return existing

    try:
        hints = get_type_hints(dataclass_type, include_extras=True)
    except (NameError, TypeError, AttributeError) as exc:
        logger.warning(
            "strict mode: cannot resolve type hints of %s (%s: %s) — its own keys are still "
            "checked, but nested keys under it are not. Ensure forward references are "
            "importable at module level.",
            dataclass_type.__qualname__,
            type(exc).__name__,
            exc,
        )
        hints = {}

    dc_fields = fields(dataclass_type)
    keys = frozenset(canonical_name(f.name) for f in dc_fields)
    node = ObjectNode(keys=keys, children={}, dc_type=dataclass_type)
    memo[dataclass_type] = node

    for f in dc_fields:
        field_type = hints.get(f.name)
        if field_type is None:
            continue
        child = _node_for_field_type(field_type, memo)
        if child is not None:
            node.children[canonical_name(f.name)] = child

    return node


@lru_cache(maxsize=128)
def known_key_tree(dataclass_type: "type[DataclassInstance]") -> ObjectNode:
    """Build the tree of keys known to *dataclass_type*, memoized per schema."""
    return _build_object_node(dataclass_type, {})


def alias_keys_by_type(field_mapping: FieldMapping | None) -> "dict[type[DataclassInstance], frozenset[str]]":
    """Extra known keys per owning dataclass type, from a source's ``field_mapping``.

    Reuses ``build_alias_map`` (the exact function ``AliasProvider`` uses) so the set of
    accepted keys matches what would actually be recognized at load time — both
    same-level (``AliasEntry``) and cross-level (``CrossLevelEntry``) aliases are read
    from the *owner*'s own dict level (see ``_apply_cross_level_entry`` in
    ``providers/alias.py``), so both are grouped under ``owner`` here.
    """
    if not field_mapping:
        return {}

    alias_map = build_alias_map(field_mapping)
    result: dict[type[DataclassInstance], set[str]] = {}
    for owner, entries in alias_map.items():
        if not (isinstance(owner, type) and is_dataclass(owner)):
            continue
        for entry in entries:
            result.setdefault(owner, set()).update(canonical_name(alias) for alias in entry.aliases)
    return {owner: frozenset(aliases) for owner, aliases in result.items()}
