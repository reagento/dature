from dataclasses import fields
from datetime import timedelta
from typing import Any, Final, cast, get_type_hints

from adaptix import NameStyle as AdaptixNameStyle
from adaptix import Retort, loader, name_mapping
from adaptix.provider import Provider

from dature.expansion.alias_provider import AliasProvider
from dature.field_path import FieldPath, resolve_nested_owner
from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
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
from dature.loaders.scalars import float_passthrough, int_from_string
from dature.protocols import DataclassInstance
from dature.skip_field_provider import ModelToDictProvider, SkipFieldProvider
from dature.sources.base import IndexedSource, Source
from dature.type_aliases import (
    URL,
    Base64UrlBytes,
    Base64UrlStr,
    FieldMapping,
    JSONValue,
    NameStyle,
    TypeLoaderMap,
)
from dature.type_utils import find_nested_dataclasses
from dature.validators.base import (
    create_metadata_validator_providers,
    create_root_validator_providers,
    create_validator_providers,
    extract_and_check_validators,
)


def get_adaptix_name_style(name_style: NameStyle | None) -> AdaptixNameStyle | None:
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
    name_style: NameStyle | None,
    field_mapping: FieldMapping | None,
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
    source: Source,
    *,
    resolved_type_loaders: TypeLoaderMap | None = None,
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


def create_retort(base_recipe: list[Provider]) -> Retort:
    return Retort(strict_coercion=True, recipe=base_recipe)


def create_probe_retort(base_recipe: list[Provider]) -> Retort:
    return Retort(
        strict_coercion=True,
        recipe=[SkipFieldProvider(), ModelToDictProvider(), *base_recipe],
    )


def create_validating_retort[T](
    source: "Source",
    schema: type[T],
    base_recipe: list[Provider],
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
            *base_recipe,
        ],
    )


_PLAIN_SENTINEL: Final[object] = object()
_VALIDATING_SENTINEL: Final[object] = object()
_PROBE_SENTINEL: Final[object] = object()


def _loaders_frozenset(resolved_type_loaders: TypeLoaderMap | None) -> frozenset[Any]:
    return frozenset(resolved_type_loaders.items()) if resolved_type_loaders is not None else frozenset()


class RetortCache:
    """Owns a single base ``Retort`` and builds/caches per-source variants via ``extend()``.

    The cache is keyed by ``(source_idx, variant, type_loaders)`` where *source_idx*
    is the stable positional index of the source in the ``Loader``'s sources tuple.
    Using an index (rather than ``id(source)`` or a UUID embedded in the source)
    lets clones of the same source share the pre-warmed retort without any
    source-level bookkeeping.
    """

    def __init__(self) -> None:
        self._base: Retort = Retort(strict_coercion=True)
        self._cache: dict[tuple[Any, ...], Retort] = {}

    def _plain_key(self, source_idx: int, type_loaders: TypeLoaderMap | None) -> tuple[int, object, frozenset[Any]]:
        return (source_idx, _PLAIN_SENTINEL, _loaders_frozenset(type_loaders))

    def _validating_key(
        self,
        source_idx: int,
        schema: type,
        type_loaders: TypeLoaderMap | None,
    ) -> tuple[int, object, int, frozenset[Any]]:
        return (source_idx, _VALIDATING_SENTINEL, id(schema), _loaders_frozenset(type_loaders))

    def _probe_key(self, source_idx: int, type_loaders: TypeLoaderMap | None) -> tuple[int, object, frozenset[Any]]:
        return (source_idx, _PROBE_SENTINEL, _loaders_frozenset(type_loaders))

    def plain(self, indexed: IndexedSource, *, resolved_type_loaders: TypeLoaderMap | None = None) -> Retort:
        """Return the plain loading retort for *indexed.source*, building and caching it on first call."""
        key = self._plain_key(indexed.index, resolved_type_loaders)
        if key not in self._cache:
            recipe = build_base_recipe(indexed.source, resolved_type_loaders=resolved_type_loaders)
            self._cache[key] = self._base.extend(recipe=recipe)
        return self._cache[key]

    def validating[T](
        self,
        indexed: IndexedSource,
        schema: type[T],
        *,
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> Retort:
        """Return the validating retort for (*indexed.source*, *schema*), building and caching it on first call."""
        key = self._validating_key(indexed.index, schema, resolved_type_loaders)
        if key not in self._cache:
            root_validator_providers = create_root_validator_providers(
                schema,
                indexed.source.root_validators or (),
            )
            metadata_validator_providers = create_metadata_validator_providers(
                indexed.source.validators or {},
            )
            self._cache[key] = self.plain(indexed, resolved_type_loaders=resolved_type_loaders).extend(
                recipe=[
                    *get_validator_providers(schema),
                    *metadata_validator_providers,
                    *root_validator_providers,
                ],
            )
        return self._cache[key]

    def probe(self, indexed: IndexedSource, *, resolved_type_loaders: TypeLoaderMap | None = None) -> Retort:
        """Return the probe (skip-field) retort for *indexed.source*, building and caching it on first call."""
        key = self._probe_key(indexed.index, resolved_type_loaders)
        if key not in self._cache:
            self._cache[key] = self.plain(indexed, resolved_type_loaders=resolved_type_loaders).extend(
                recipe=[SkipFieldProvider(), ModelToDictProvider()],
            )
        return self._cache[key]

    def load[T: DataclassInstance](
        self,
        indexed: IndexedSource,
        data: JSONValue,
        schema: type[T],
        *,
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> T:
        """Load *data* into *schema* using the plain retort for *indexed.source*."""
        return self.plain(indexed, resolved_type_loaders=resolved_type_loaders).load(data, schema)
