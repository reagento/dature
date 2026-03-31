from typing import Annotated, Any, get_args, get_origin

from adaptix import P, validator
from adaptix.provider import Provider

from dature.expansion.alias_provider import resolve_nested_owner
from dature.field_path import FieldPath
from dature.protocols import DataclassInstance, ValidatorProtocol
from dature.types import FieldValidators


def extract_validators_from_type(field_type: Any) -> list[ValidatorProtocol]:  # noqa: ANN401
    validators: list[ValidatorProtocol] = []

    if get_origin(field_type) is not Annotated:
        return validators

    args = get_args(field_type)

    validators.extend(arg for arg in args[1:] if hasattr(arg, "__dataclass_fields__"))

    return validators


def create_validator_providers(
    schema: type,
    field_name: str,
    validators: list[ValidatorProtocol],
) -> list[Provider]:
    providers = []

    for v in validators:
        func = v.get_validator_func()
        error = v.get_error_message()
        provider = validator(
            P[schema][field_name],
            func,
            error,
        )
        providers.append(provider)

    return providers


def _normalize_validators(
    value: ValidatorProtocol | tuple[ValidatorProtocol, ...],
) -> list[ValidatorProtocol]:
    if isinstance(value, tuple):
        return list(value)
    return [value]


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

        normalized = _normalize_validators(validators_value)

        if len(field_path_key.parts) > 1:
            if isinstance(field_path_key.owner, str):
                msg = (
                    f"Nested FieldPath with string owner '{field_path_key.owner}' "
                    f"is not supported — cannot resolve intermediate types"
                )
                raise TypeError(msg)
            owner: type[DataclassInstance] = resolve_nested_owner(field_path_key.owner, field_path_key.parts[:-1])
        else:
            if isinstance(field_path_key.owner, str):
                msg = (
                    f"FieldPath with string owner '{field_path_key.owner}' "
                    f"is not supported for validators — use a type reference"
                )
                raise TypeError(msg)
            owner = field_path_key.owner

        field_name = field_path_key.parts[-1]
        field_providers = create_validator_providers(owner, field_name, normalized)
        providers.extend(field_providers)

    return providers


def create_root_validator_providers(
    schema: type,
    root_validators: tuple[ValidatorProtocol, ...],
) -> list[Provider]:
    providers = []

    for root_validator in root_validators:
        provider = validator(
            P[schema],
            root_validator.get_validator_func(),
            root_validator.get_error_message(),
        )
        providers.append(provider)

    return providers
