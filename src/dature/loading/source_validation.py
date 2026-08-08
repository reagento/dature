"""Declarative post-merge source validation — replaces the removed ``check_invariants`` hook.

``validate_source`` runs at the same point ``check_invariants()`` used to: after config-group
merge and cross-ref interpolation, before the source is loaded. It checks three declarative
mechanisms a ``Source`` subclass may use to express invariants:

1. ``Literal[...]``-typed fields (including ``Literal[...] | None``) — the value must be one
   of the declared choices, or ``None`` if the field is optional.
2. ``Annotated[..., V ...]`` field predicates — reuses ``extract_and_check_validators`` so the
   same predicates that ``load()`` would enforce on a loaded value are enforced here too.
3. ``root_validators`` — a ``ClassVar[tuple[RootPredicate, ...]]`` of ``V.root(...)`` checks
   for required-ness and cross-field constraints, run against the source instance itself.
"""

import types
import typing
from dataclasses import fields
from typing import Literal, get_args, get_origin, get_type_hints

from dature.sources.protocol import SourceProtocol
from dature.validators.base import extract_and_check_validators


def _literal_choices(field_type: object) -> "tuple[object, ...] | None":
    """Return the ``Literal[...]`` choices for *field_type*, unwrapping ``X | None``."""
    if get_origin(field_type) is Literal:
        return get_args(field_type)
    if get_origin(field_type) in (types.UnionType, typing.Union):
        for arg in get_args(field_type):
            if get_origin(arg) is Literal:
                return get_args(arg)
    return None


def validate_source(source: SourceProtocol) -> None:
    """Enforce a source's declarative invariants; raise ``ValueError`` on the first violation.

    Called after config-group merge and cross-ref interpolation
    (``merge_runtime.LoadCtx._prepare_source_and_check_enabled`` and the single-source path in
    ``loader.Loader``), so ``None``/``""`` init-fields have already been filled from
    ``dature.config.<config_group>`` where applicable.

    Not to be confused with the ``root_validators=`` parameter of ``load()`` / ``Loader``,
    which validates the merged *schema instance* after loading — this validates the
    *source* itself, before it is loaded.
    """
    cls = type(source)
    class_name = cls.__name__
    type_hints = get_type_hints(cls, include_extras=True)

    for f in fields(source):
        if not f.init or f.name not in type_hints:
            continue
        value = getattr(source, f.name)
        if value is None:
            continue
        field_type = type_hints[f.name]

        choices = _literal_choices(field_type)
        if choices is not None and value not in choices:
            rendered = ", ".join(repr(choice) for choice in choices)
            msg = f"{class_name}: {f.name} must be one of {rendered}, got {value!r}"
            raise ValueError(msg)

        for predicate in extract_and_check_validators(field_type, field_path=[f.name]):
            if not predicate.get_validator_func()(value):
                msg = f"{class_name}: {predicate.get_error_message()}"
                raise ValueError(msg)

    for root_predicate in cls.root_validators:
        if not root_predicate.get_validator_func()(source):
            msg = f"{class_name}: {root_predicate.get_error_message()}"
            raise ValueError(msg)
