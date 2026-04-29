from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Annotated, Any, cast, get_args, get_origin, get_type_hints

from adaptix import P, validator
from adaptix.load_error import AggregateLoadError, ValidationLoadError
from adaptix.provider import Provider
from adaptix.struct_trail import append_trail

from dature.expansion.alias_provider import resolve_nested_owner
from dature.field_path import FieldPath
from dature.types import FieldValidators
from dature.validators.collection import EachPredicate
from dature.validators.predicate import AndPredicate, Predicate
from dature.validators.root import RootPredicate

if TYPE_CHECKING:
    from dature.protocols import DataclassInstance


def _flatten(predicate: Predicate) -> list[Predicate]:
    """Flatten AndPredicate trees into a flat list of leaf predicates.

    ``A & B & C`` produces three independent providers, matching adaptix behaviour
    where multiple validators on the same field must all pass. ``Or`` / ``Not`` /
    leaves stay as single providers.
    """
    if isinstance(predicate, AndPredicate):
        return _flatten(predicate.left) + _flatten(predicate.right)
    return [predicate]


def extract_and_check_validators(
    field_type: Any,  # noqa: ANN401
    *,
    field_path: list[str],
) -> list[Predicate]:
    if get_origin(field_type) is not Annotated:
        return []

    predicates: list[Predicate] = []
    for arg in get_args(field_type)[1:]:
        if isinstance(arg, RootPredicate):
            msg = "V.root(...) must be passed via source.root_validators, not placed in Annotated[...] metadata"
            raise TypeError(msg)
        if not isinstance(arg, Predicate):
            continue
        arg.check_type(field_type, field_path=field_path)
        predicates.extend(_flatten(arg))

    return predicates


def _make_each_provider(location: Any, each: EachPredicate) -> Provider:  # noqa: ANN401
    inner_func = each.inner.get_validator_func()
    inner_msg = each.inner.get_error_message()

    def all_pass(val: Any) -> bool:  # noqa: ANN401
        return all(inner_func(elem) for elem in val)

    def build_error(val: Any) -> AggregateLoadError:  # noqa: ANN401
        sub_errors: list[ValidationLoadError] = []
        for idx, elem in enumerate(val):
            if not inner_func(elem):
                sub = ValidationLoadError(inner_msg, elem)
                append_trail(sub, idx)
                sub_errors.append(sub)
        return AggregateLoadError(each.get_error_message(), tuple(sub_errors))

    return validator(location, all_pass, build_error)


def _make_provider(location: Any, predicate: Predicate) -> Provider:  # noqa: ANN401
    if isinstance(predicate, EachPredicate):
        return _make_each_provider(location, predicate)
    return validator(
        location,
        predicate.get_validator_func(),
        predicate.get_error_message(),
    )


def create_validator_providers(
    schema: type,
    field_name: str,
    predicates: list[Predicate],
) -> list[Provider]:
    location = P[schema][field_name]
    return [_make_provider(location, p) for p in predicates]


def _normalize_metadata_value(
    value: Predicate | tuple[Predicate, ...],
) -> list[Predicate]:
    if isinstance(value, tuple):
        raw = list(value)
    else:
        raw = [value]
    for p in raw:
        if isinstance(p, RootPredicate):
            msg = "V.root(...) cannot be used in source.validators — pass it via source.root_validators instead"
            raise TypeError(msg)
        if not isinstance(p, Predicate):
            msg = f"source.validators value must be a V-predicate, got {type(p).__name__}"
            raise TypeError(msg)
    return raw


def create_metadata_validator_providers(
    field_validators: FieldValidators,
) -> list[Provider]:
    providers: list[Provider] = []

    for field_path_key, validators_value in field_validators.items():
        if not isinstance(field_path_key, FieldPath):
            msg = f"validators key must be a FieldPath, got {type(field_path_key).__name__}"
            raise TypeError(msg)

        if len(field_path_key.parts) == 0:
            msg = "FieldPath must contain at least one field name"
            raise ValueError(msg)

        raw_predicates = _normalize_metadata_value(validators_value)

        if len(field_path_key.parts) > 1:
            if isinstance(field_path_key.owner, str):
                msg = (
                    f"Nested FieldPath with string owner '{field_path_key.owner}' "
                    f"is not supported — cannot resolve intermediate types"
                )
                raise TypeError(msg)
            owner: type[DataclassInstance] = resolve_nested_owner(
                field_path_key.owner,
                field_path_key.parts[:-1],
            )
        else:
            if isinstance(field_path_key.owner, str):
                msg = (
                    f"FieldPath with string owner '{field_path_key.owner}' "
                    f"is not supported for validators — use a type reference"
                )
                raise TypeError(msg)
            owner = field_path_key.owner

        field_name = field_path_key.parts[-1]

        type_hints = get_type_hints(cast("type", owner), include_extras=True)
        checked_predicates: list[Predicate] = []
        field_type = type_hints.get(field_name)
        for predicate in raw_predicates:
            if field_type is not None:
                predicate.check_type(field_type, field_path=list(field_path_key.parts))
            checked_predicates.extend(_flatten(predicate))

        field_providers = create_validator_providers(owner, field_name, checked_predicates)
        providers.extend(field_providers)

    return providers


def create_root_validator_providers(
    schema: type,
    root_validators: Iterable[RootPredicate],
) -> list[Provider]:
    if isinstance(root_validators, (str, bytes, Mapping)):
        msg = f"source.root_validators must be a sequence of V.root(...) objects, got {type(root_validators).__name__}."
        raise TypeError(msg)
    try:
        items = tuple(root_validators)
    except TypeError as exc:
        msg = (
            f"source.root_validators must be iterable (tuple, list, ...), "
            f"got {type(root_validators).__name__}. "
            "A common mistake is forgetting the trailing comma — "
            "use `root_validators=(V.root(check),)` for a single validator."
        )
        raise TypeError(msg) from exc

    providers = []
    for root_predicate in items:
        if isinstance(root_predicate, Predicate):
            msg = (
                f"source.root_validators received a field-level predicate "
                f"({type(root_predicate).__name__}). Use V.root(func) for cross-field "
                "validation, or move field-level predicates into source.validators."
            )
            raise TypeError(msg)
        if not isinstance(root_predicate, RootPredicate):
            msg = f"source.root_validators must contain V.root(...) objects, got {type(root_predicate).__name__}"
            raise TypeError(msg)
        provider = validator(
            P[schema],
            root_predicate.get_validator_func(),
            root_predicate.get_error_message(),
        )
        providers.append(provider)

    return providers
