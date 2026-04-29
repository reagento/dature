from dataclasses import fields
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, cast, get_type_hints

from adaptix import NameStyle as AdaptixNameStyle
from adaptix import Retort, loader, name_mapping
from adaptix.provider import Provider

from dature.expansion.alias_provider import AliasProvider, resolve_nested_owner
from dature.field_path import FieldPath
from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.loaders import (
    bool_loader,
    bytearray_from_json_string,
    date_from_string,
    datetime_from_string,
    float_from_string,
    none_from_empty_string,
    optional_from_empty_string,
    str_from_scalar,
    time_from_string,
)
from dature.loaders.base import (
    base64url_bytes_from_string,
    base64url_str_from_string,
    byte_size_from_string,
    bytes_from_string,
    complex_from_string,
    payment_card_number_from_string,
    secret_str_from_string,
    timedelta_from_string,
    url_from_string,
)
from dature.loaders.common import float_passthrough, int_from_string
from dature.skip_field_provider import ModelToDictProvider, SkipFieldProvider
from dature.type_utils import find_nested_dataclasses
from dature.types import (
    URL,
    Base64UrlBytes,
    Base64UrlStr,
)
from dature.validators.base import (
    create_metadata_validator_providers,
    create_root_validator_providers,
    create_validator_providers,
    extract_and_check_validators,
)

if TYPE_CHECKING:
    from dature.protocols import DataclassInstance
    from dature.sources.base import Source
    from dature.types import (
        FieldMapping,
        JSONValue,
        NameStyle,
        TypeLoaderMap,
    )


def string_value_loaders() -> list[Provider]:
    return [
        loader(str, str_from_scalar),
        loader(float, float_from_string),
        loader(date, date_from_string),
        loader(datetime, datetime_from_string),
        loader(time, time_from_string),
        loader(bytearray, bytearray_from_json_string),
        loader(type(None), none_from_empty_string),
        loader(str | None, optional_from_empty_string),
        loader(bool, bool_loader),
    ]


def get_adaptix_name_style(name_style: "NameStyle | None") -> AdaptixNameStyle | None:
    if name_style is None:
        return None

    name_style_map = {
        "lower_snake": AdaptixNameStyle.LOWER_SNAKE,
        "upper_snake": AdaptixNameStyle.UPPER_SNAKE,
        "lower_camel": AdaptixNameStyle.CAMEL,
        "upper_camel": AdaptixNameStyle.PASCAL,
        "lower_kebab": AdaptixNameStyle.LOWER_KEBAB,
        "upper_kebab": AdaptixNameStyle.UPPER_KEBAB,
    }
    return name_style_map.get(name_style)


def get_name_mapping_providers(
    name_style: "NameStyle | None",
    field_mapping: "FieldMapping | None",
) -> list[Provider]:
    providers: list[Provider] = []

    adaptix_name_style = get_adaptix_name_style(name_style)
    if adaptix_name_style is not None:
        providers.append(name_mapping(name_style=adaptix_name_style))

    if field_mapping:
        owner_fields: dict[type[DataclassInstance] | str, dict[str, str]] = {}
        for field_path_key in field_mapping:
            if not isinstance(field_path_key, FieldPath):
                continue
            owner: type[DataclassInstance] | str = field_path_key.owner
            if len(field_path_key.parts) > 1 and not isinstance(field_path_key.owner, str):
                owner = resolve_nested_owner(field_path_key.owner, field_path_key.parts[:-1])
            field_name = field_path_key.parts[-1]
            if owner not in owner_fields:
                owner_fields[owner] = {}
            owner_fields[owner][field_name] = field_name

        for owner, identity_map in owner_fields.items():
            if isinstance(owner, str):
                providers.append(name_mapping(map=identity_map))
            else:
                providers.append(name_mapping(owner, map=identity_map))

        providers.append(AliasProvider(field_mapping))

    return providers


def get_validator_providers[T](schema: type[T]) -> list[Provider]:
    providers: list[Provider] = []
    type_hints = get_type_hints(schema, include_extras=True)

    for f in fields(cast("type[DataclassInstance]", schema)):
        if f.name not in type_hints:
            continue

        field_type = type_hints[f.name]
        validators_list = extract_and_check_validators(field_type, field_path=[f.name])

        if validators_list:
            field_providers = create_validator_providers(schema, f.name, validators_list)
            providers.extend(field_providers)

        for nested_dc in find_nested_dataclasses(field_type):
            nested_providers = get_validator_providers(nested_dc)
            providers.extend(nested_providers)

    return providers


def build_base_recipe(
    source: "Source",
    *,
    resolved_type_loaders: "TypeLoaderMap | None" = None,
) -> list[Provider]:
    user_loaders: list[Provider] = [
        loader(type_, func) for type_, func in (resolved_type_loaders or source.type_loaders or {}).items()
    ]
    default_loaders: list[Provider] = [
        loader(int, int_from_string),
        loader(float, float_passthrough),
        loader(bytes, bytes_from_string),
        loader(complex, complex_from_string),
        loader(timedelta, timedelta_from_string),
        loader(URL, url_from_string),
        loader(Base64UrlBytes, base64url_bytes_from_string),
        loader(Base64UrlStr, base64url_str_from_string),
        loader(SecretStr, secret_str_from_string),
        loader(PaymentCardNumber, payment_card_number_from_string),
        loader(ByteSize, byte_size_from_string),
    ]
    return [
        *user_loaders,
        *source.additional_loaders(),
        *default_loaders,
        *get_name_mapping_providers(source.name_style, source.field_mapping),
    ]


def create_retort(
    source: "Source",
    *,
    resolved_type_loaders: "TypeLoaderMap | None" = None,
) -> Retort:
    return Retort(
        strict_coercion=True,
        recipe=build_base_recipe(source, resolved_type_loaders=resolved_type_loaders),
    )


def create_probe_retort(
    source: "Source",
    *,
    resolved_type_loaders: "TypeLoaderMap | None" = None,
) -> Retort:
    return Retort(
        strict_coercion=True,
        recipe=[
            SkipFieldProvider(),
            ModelToDictProvider(),
            *build_base_recipe(source, resolved_type_loaders=resolved_type_loaders),
        ],
    )


def create_validating_retort[T](
    source: "Source",
    schema: type[T],
    *,
    resolved_type_loaders: "TypeLoaderMap | None" = None,
) -> Retort:
    root_validator_providers = create_root_validator_providers(
        schema,
        source.root_validators or (),
    )
    metadata_validator_providers = create_metadata_validator_providers(
        source.validators or {},
    )
    return Retort(
        strict_coercion=True,
        recipe=[
            *get_validator_providers(schema),
            *metadata_validator_providers,
            *root_validator_providers,
            *build_base_recipe(source, resolved_type_loaders=resolved_type_loaders),
        ],
    )


def _retort_cache_key(
    schema: type,
    resolved_type_loaders: "TypeLoaderMap | None",
) -> tuple[type, frozenset[tuple[type, Any]]]:
    loaders_key = frozenset(resolved_type_loaders.items()) if resolved_type_loaders is not None else frozenset()
    return (schema, loaders_key)


def transform_to_dataclass[T](
    source: "Source",
    data: "JSONValue",
    schema: type[T],
    *,
    resolved_type_loaders: "TypeLoaderMap | None" = None,
) -> T:
    key = _retort_cache_key(schema, resolved_type_loaders)
    if key not in source.retorts:
        source.retorts[key] = create_retort(source, resolved_type_loaders=resolved_type_loaders)
    return source.retorts[key].load(data, schema)


def ensure_retort(
    source: "Source",
    cls: "type[DataclassInstance]",
    *,
    resolved_type_loaders: "TypeLoaderMap | None" = None,
) -> None:
    key = _retort_cache_key(cls, resolved_type_loaders)
    if key not in source.retorts:
        source.retorts[key] = create_retort(source, resolved_type_loaders=resolved_type_loaders)
    source.retorts[key].get_loader(cls)
