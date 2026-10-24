"""adaptix recipes and precomputed retorts that dature's loader pipeline is built from."""

from datetime import timedelta
from typing import Final

from adaptix import DebugTrail, Retort, loader, name_mapping
from adaptix import NameStyle as AdaptixNameStyle
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
from dature.field_path import FieldPath, resolve_nested_owner
from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.protocols import DataclassInstance
from dature.providers.alias import AliasProvider
from dature.providers.compiler import TrackingModelLoaderProvider
from dature.providers.model import ImplicitNestedDefaultProvider
from dature.providers.typed_dict import TypedDictModelLoaderProvider
from dature.sources.base import bytes_value_loaders, remote_value_loaders, string_value_loaders
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import (
    URL,
    Base64UrlBytes,
    Base64UrlStr,
    FieldMapping,
    NameStyle,
    TypeLoaderMap,
)


def get_adaptix_name_style(name_style: NameStyle | None) -> AdaptixNameStyle | None:
    if name_style is None:
        return None

    match name_style:
        case "lower_snake":
            return AdaptixNameStyle.LOWER_SNAKE
        case "upper_snake":
            return AdaptixNameStyle.UPPER_SNAKE
        case "lower_camel":
            return AdaptixNameStyle.CAMEL
        case "upper_camel":
            return AdaptixNameStyle.PASCAL
        case "lower_kebab":
            return AdaptixNameStyle.LOWER_KEBAB
        case "upper_kebab":
            return AdaptixNameStyle.UPPER_KEBAB
        case _ as unknown:
            msg = f"Unknown name_style: {unknown!r}"
            raise ValueError(msg)


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
            if not isinstance(field_path_key, FieldPath) or not field_path_key.parts:
                continue
            owner: type[DataclassInstance] | str = field_path_key.owner
            parts = field_path_key.parts
            has_nested_parts = len(parts) > 1
            if has_nested_parts and not isinstance(field_path_key.owner, str):
                owner = resolve_nested_owner(field_path_key.owner, parts[:-1])
            field_name = parts[-1]
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


_DEFAULT_LOADERS: Final[tuple[Provider, ...]] = (
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
)


def build_base_recipe(
    source: SourceProtocol,
    *,
    resolved_type_loaders: TypeLoaderMap | None = None,
) -> list[Provider]:
    user_loaders: list[Provider] = [
        loader(type_, func) for type_, func in (resolved_type_loaders or source.type_loaders or {}).items()
    ]
    return [
        *user_loaders,
        *source.format_loaders(),
        *_DEFAULT_LOADERS,
        *get_name_mapping_providers(source.name_style, source.field_mapping),
    ]


# Two shared base retorts differing only in debug_trail. The FAST base (DebugTrail.DISABLE)
# generates leaner loader code — ~30% cheaper to compile — but its errors carry no field-path
# trail. The RICH base (DebugTrail.ALL) is the historical behaviour and produces the trailed
# AggregateLoadError that dature's error extraction relies on. The happy path loads through FAST;
# on any failure the load is replayed through RICH (built lazily) to obtain the trailed error.
# Both hold no schema-/source-specific state; all customisation is added via .extend().
#
# TrackingModelLoaderProvider() is baked in here, as the base's own (lowest-priority) instance
# recipe, rather than appended inside build_base_recipe(): every later .extend() call (recipe,
# overrides, root validators, skip/field-pass providers, ...) prepends ahead of whatever the base
# already has, so this guarantees it is always checked dead last among dature's own providers —
# exactly where adaptix's own built-in ModelLoaderProvider naturally sits relative to them. Adding
# it to build_base_recipe's own returned list is not equivalent: callers that append more
# providers (e.g. ConstructorOverrideProvider, root validators in _final_raw) after that list have
# their own providers wrongly checked *after* the catch-all instead of before it.
BASE_FAST: Final[Retort] = Retort(strict_coercion=True, debug_trail=DebugTrail.DISABLE).extend(
    recipe=[TypedDictModelLoaderProvider(), ImplicitNestedDefaultProvider(), TrackingModelLoaderProvider()]
)
BASE_RICH: Final[Retort] = Retort(strict_coercion=True, debug_trail=DebugTrail.ALL).extend(
    recipe=[TypedDictModelLoaderProvider(), ImplicitNestedDefaultProvider(), TrackingModelLoaderProvider()]
)

# Precomputed FAST retorts for the two built-in "uncustomized" default recipes (string-value
# sources like EnvSource/CLI vs. plain sources like JSON/TOML/YAML). Sources with no
# type_loaders/name_style/field_mapping and no constructor override/root validators reuse one
# of these instead of paying `.extend()` on every cold load (see `uncustomized_fast_retort`).
# Only FAST is precomputed: RICH only compiles on the rare error-replay path, so precomputing
# it would add import cost without a happy-path payoff.
FAST_STRING: Final[Retort] = BASE_FAST.extend(recipe=[*string_value_loaders(), *_DEFAULT_LOADERS])
FAST_BYTES: Final[Retort] = BASE_FAST.extend(recipe=[*bytes_value_loaders(), *_DEFAULT_LOADERS])
FAST_REMOTE: Final[Retort] = BASE_FAST.extend(recipe=[*remote_value_loaders(), *_DEFAULT_LOADERS])
FAST_PLAIN: Final[Retort] = BASE_FAST.extend(recipe=[*_DEFAULT_LOADERS])


def uncustomized_fast_retort(source: SourceProtocol) -> Retort | None:
    """Return a precomputed FAST retort for *source* if it needs no per-call ``.extend()``."""
    if source.type_loaders or source.name_style or source.field_mapping:
        return None
    additional = source.format_loaders()
    if additional == string_value_loaders():
        return FAST_STRING
    if additional == bytes_value_loaders():
        return FAST_BYTES
    if additional == remote_value_loaders():
        return FAST_REMOTE
    if not additional:
        return FAST_PLAIN
    return None
