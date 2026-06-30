from collections.abc import Iterable
from datetime import timedelta
from typing import Any, Final

from adaptix import NameStyle as AdaptixNameStyle
from adaptix import Retort, loader, name_mapping
from adaptix.provider import Provider

from dature.coercion.base import (
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
from dature.coercion.scalars import float_passthrough, int_from_string
from dature.expansion.alias_provider import AliasProvider
from dature.field_path import FieldPath, resolve_nested_owner
from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.protocols import DataclassInstance
from dature.skip_field_provider import ModelToDictProvider, SkipFieldProvider
from dature.sources.base import IndexedSource, Source
from dature.type_aliases import (
    URL,
    Base64UrlBytes,
    Base64UrlStr,
    FieldMapping,
    NameStyle,
    TypeLoaderMap,
)
from dature.validators.base import (
    create_metadata_validator_providers,
    create_root_validator_providers,
    get_validator_providers,
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


_PLAIN_SENTINEL: Final[object] = object()
_FIELD_PASS_SKIP_SENTINEL: Final[object] = object()
_FIELD_PASS_NOSKIP_SENTINEL: Final[object] = object()
_ROOT_SENTINEL: Final[object] = object()


def _loaders_frozenset(resolved_type_loaders: TypeLoaderMap | None) -> frozenset[Any]:
    return frozenset(resolved_type_loaders.items()) if resolved_type_loaders is not None else frozenset()


class RetortCache:
    """Owns a single base ``Retort`` and builds/caches per-source variants via ``extend()``.

    The cache is keyed by ``(source_idx, variant, type_loaders)`` where *source_idx*
    is the stable positional index of the source in the ``Loader``'s sources tuple.
    Using an index (rather than ``id(source)`` or a UUID embedded in the source)
    lets clones of the same source share the pre-warmed retort without any
    source-level bookkeeping.

    *schema* is fixed for the lifetime of this cache (one ``RetortCache`` per ``Loader``).
    ``_has_annotated_field_validators`` is computed once at construction time, not lazily
    per call, so there is no per-call id(schema) lookup.
    """

    def __init__[T](self, schema: type[T], *, root_validators: Iterable[Any] = ()) -> None:
        self._base: Retort = Retort(strict_coercion=True)
        self._cache: dict[tuple[Any, ...], Retort] = {}
        self._schema = schema
        self._has_annotated_field_validators: bool = bool(get_validator_providers(schema))
        self._root_providers: list[Any] = create_root_validator_providers(schema, root_validators)

    def _plain_key(self, source_idx: int, type_loaders: TypeLoaderMap | None) -> tuple[int, object, frozenset[Any]]:
        return (source_idx, _PLAIN_SENTINEL, _loaders_frozenset(type_loaders))

    def _field_pass_key(
        self,
        source_idx: int,
        skip: bool,  # noqa: FBT001
        type_loaders: TypeLoaderMap | None,
    ) -> tuple[int, object, frozenset[Any]]:
        sentinel = _FIELD_PASS_SKIP_SENTINEL if skip else _FIELD_PASS_NOSKIP_SENTINEL
        return (source_idx, sentinel, _loaders_frozenset(type_loaders))

    def _root_key(self, source_idx: int, type_loaders: TypeLoaderMap | None) -> tuple[int, object, frozenset[Any]]:
        return (source_idx, _ROOT_SENTINEL, _loaders_frozenset(type_loaders))

    def plain(self, indexed: IndexedSource, *, resolved_type_loaders: TypeLoaderMap | None = None) -> Retort:
        """Return the plain loading retort for *indexed.source*, building and caching it on first call."""
        key = self._plain_key(indexed.index, resolved_type_loaders)
        if key not in self._cache:
            recipe = build_base_recipe(indexed.source, resolved_type_loaders=resolved_type_loaders)
            self._cache[key] = self._base.extend(recipe=recipe)
        return self._cache[key]

    def field_pass(
        self,
        indexed: IndexedSource,
        *,
        skip: bool,
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> Retort:
        """Return a per-source field-validating retort that produces a ``dict`` keyed by field name.

        Runs on the source's own raw dict (not the cumulative merged state).  Fields absent
        from the raw dict are left as ``NOT_LOADED`` by ``ModelToDictProvider`` — their
        validators do not fire and no missing-field error is raised.

        When *skip* is ``True`` (i.e. ``source.skip_field_if_invalid``), ``SkipFieldProvider``
        is prepended to the recipe so that fields whose coercion *or validation* fails are
        silently dropped (``NOT_LOADED``) rather than raising.  This extends the old probe
        behaviour — which only checked coercibility — to also drop business-rule violations.
        """
        key = self._field_pass_key(indexed.index, skip, resolved_type_loaders)
        if key not in self._cache:
            source = indexed.source
            schema = self._schema
            skip_provider: list[Any] = [SkipFieldProvider()] if skip else []
            metadata_validator_providers = create_metadata_validator_providers(source.validators or {})
            # When skip=True (probe mode), ModelToDictProvider must apply to ALL nested
            # dataclasses so each nested field can be individually pruned.
            # When skip=False (validate mode), restrict to the top-level schema so that
            # validators on Annotated[NestedDC, V.check(...)] receive real instances.
            to_dict_provider = ModelToDictProvider() if skip else ModelToDictProvider(schema)
            self._cache[key] = self.plain(indexed, resolved_type_loaders=resolved_type_loaders).extend(
                recipe=[
                    *skip_provider,
                    *get_validator_providers(schema),
                    *metadata_validator_providers,
                    to_dict_provider,
                ],
            )
        return self._cache[key]

    def root_retort(
        self,
        indexed: IndexedSource,
        *,
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> Retort:
        """Return the final-construction retort: plain coercion + schema-level root validators.

        This is used once at the end of loading (single or multi source) to build the
        dataclass instance and run any ``root_validators`` passed to ``load()`` / ``Loader``.
        When no root validators are configured this is identical to ``plain()``.
        """
        key = self._root_key(indexed.index, resolved_type_loaders)
        if key not in self._cache:
            self._cache[key] = self.plain(indexed, resolved_type_loaders=resolved_type_loaders).extend(
                recipe=[*self._root_providers],
            )
        return self._cache[key]

    def has_validators(self, indexed: IndexedSource) -> bool:
        """Return ``True`` when the source or schema has field validators requiring a ``field_pass``.

        Root validators are schema-level and are not considered here — they always run
        via ``root_retort()`` at the end regardless of this flag.
        """
        source = indexed.source
        return self._has_annotated_field_validators or bool(source.validators)
