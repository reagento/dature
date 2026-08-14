from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import fields, is_dataclass
from datetime import timedelta
from enum import Flag
from typing import Any, Final, Literal, cast, get_type_hints, overload

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
from dature.expansion.alias_provider import AliasProvider
from dature.field_path import FieldPath, resolve_nested_owner
from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.protocols import DataclassInstance
from dature.skip_field_provider import ConstructorOverrideProvider, ModelToDictProvider, SkipFieldProvider
from dature.sources.base import IndexedSource, bytes_value_loaders, remote_value_loaders, string_value_loaders
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import (
    URL,
    Base64UrlBytes,
    Base64UrlStr,
    FieldMapping,
    NameStyle,
    TypeLoaderMap,
)
from dature.validators.base import (
    create_root_validator_providers,
    extract_and_check_validators,
    get_validator_providers,
)
from dature.validators.predicate import Predicate


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


_PLAIN_SENTINEL: Final[object] = object()
_FIELD_PASS_SKIP_SENTINEL: Final[object] = object()
_FIELD_PASS_NOSKIP_SENTINEL: Final[object] = object()
_FINAL_SENTINEL: Final[object] = object()

# Two shared base retorts differing only in debug_trail. The FAST base (DebugTrail.DISABLE)
# generates leaner loader code — ~30% cheaper to compile — but its errors carry no field-path
# trail. The RICH base (DebugTrail.ALL) is the historical behaviour and produces the trailed
# AggregateLoadError that dature's error extraction relies on. The happy path loads through FAST;
# on any failure the load is replayed through RICH (built lazily) to obtain the trailed error.
# Both hold no schema-/source-specific state; all customisation is added via .extend().
_BASE_FAST: Final[Retort] = Retort(strict_coercion=True, debug_trail=DebugTrail.DISABLE)
_BASE_RICH: Final[Retort] = Retort(strict_coercion=True, debug_trail=DebugTrail.ALL)

# Precomputed FAST retorts for the two built-in "uncustomized" default recipes (string-value
# sources like EnvSource/CLI vs. plain sources like JSON/TOML/YAML). Sources with no
# type_loaders/name_style/field_mapping and no constructor override/root validators reuse one
# of these instead of paying `.extend()` on every cold load (see `_uncustomized_fast_retort`).
# Only FAST is precomputed: RICH only compiles on the rare error-replay path, so precomputing
# it would add import cost without a happy-path payoff.
_FAST_STRING: Final[Retort] = _BASE_FAST.extend(recipe=[*string_value_loaders(), *_DEFAULT_LOADERS])
_FAST_BYTES: Final[Retort] = _BASE_FAST.extend(recipe=[*bytes_value_loaders(), *_DEFAULT_LOADERS])
_FAST_REMOTE: Final[Retort] = _BASE_FAST.extend(recipe=[*remote_value_loaders(), *_DEFAULT_LOADERS])
_FAST_PLAIN: Final[Retort] = _BASE_FAST.extend(recipe=[*_DEFAULT_LOADERS])


def _uncustomized_fast_retort(source: SourceProtocol) -> Retort | None:
    """Return a precomputed FAST retort for *source* if it needs no per-call ``.extend()``."""
    if source.type_loaders or source.name_style or source.field_mapping:
        return None
    additional = source.format_loaders()
    if additional == string_value_loaders():
        return _FAST_STRING
    if additional == bytes_value_loaders():
        return _FAST_BYTES
    if additional == remote_value_loaders():
        return _FAST_REMOTE
    if not additional:
        return _FAST_PLAIN
    return None


class _DualRetort:
    """Facade over a FAST (DebugTrail.DISABLE) retort with a lazy RICH (DebugTrail.ALL) fallback."""

    __slots__ = ("_fast", "_rich_factory")

    def __init__(self, fast: Retort, rich_factory: Callable[[], Retort]) -> None:
        self._fast = fast
        self._rich_factory = rich_factory

    def load[T](self, data: Any, tp: type[T]) -> T:  # noqa: ANN401
        with suppress(Exception):
            return self._fast.load(data, tp)
        return self._rich_factory().load(data, tp)

    def get_loader(self, tp: Any) -> Callable[[Any], Any]:  # noqa: ANN401
        fast_loader = self._fast.get_loader(tp)
        rich_factory = self._rich_factory

        def _dual(data: Any) -> Any:  # noqa: ANN401
            with suppress(Exception):
                return fast_loader(data)
            return rich_factory().get_loader(tp)(data)

        return _dual


def _loaders_frozenset(resolved_type_loaders: TypeLoaderMap | None) -> frozenset[Any]:
    return frozenset(resolved_type_loaders.items()) if resolved_type_loaders is not None else frozenset()


def _compute_flag_field_names[T](schema: type[T]) -> frozenset[str]:
    """Return the names of top-level *schema* fields whose type is an ``enum.Flag`` subclass.

    Pure static reflection — computed once per ``RetortCache`` so ``coerce_flag_fields`` does
    not call ``get_type_hints`` on every load.  Non-dataclass schemas yield an empty set.
    """
    if not is_dataclass(schema):
        return frozenset()
    try:
        type_hints = get_type_hints(cast("type[DataclassInstance]", schema))
    except Exception:  # noqa: BLE001
        return frozenset()
    names: set[str] = set()
    for field in fields(cast("type[DataclassInstance]", schema)):
        hint = type_hints.get(field.name)
        if isinstance(hint, type) and issubclass(hint, Flag):
            names.add(field.name)
    return frozenset(names)


def _compute_annotated_default_fields[T](schema: type[T]) -> tuple[tuple[str, list[Predicate]], ...]:
    """Return ``(field_name, predicates)`` for top-level *schema* fields with ``Annotated`` validators.

    Pure static reflection — computed once per ``RetortCache``.  At load time
    ``compute_default_fallback_errors`` only filters this list by the set of fields a source
    actually provided, avoiding a per-load ``get_type_hints`` + validator extraction.
    """
    if not is_dataclass(schema):
        return ()
    try:
        type_hints = get_type_hints(cast("type[DataclassInstance]", schema), include_extras=True)
    except Exception:  # noqa: BLE001
        return ()
    result: list[tuple[str, list[Predicate]]] = []
    for field in fields(cast("type[DataclassInstance]", schema)):
        field_type = type_hints.get(field.name)
        if field_type is None:
            continue
        predicates = extract_and_check_validators(field_type, field_path=[field.name])
        if predicates:
            result.append((field.name, predicates))
    return tuple(result)


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

    def __init__[T](
        self,
        schema: type[T],
        *,
        root_validators: Iterable[Any] = (),
        cache_engine: bool = False,
        metadata_providers: list[list[Provider]] | None = None,
    ) -> None:
        self._cache: dict[tuple[Any, ...], Retort] = {}
        self._cache_engine = cache_engine
        self._schema = schema
        self._has_annotated_field_validators: bool = bool(get_validator_providers(schema))
        self._root_providers: list[Any] = create_root_validator_providers(schema, root_validators)
        self._metadata_providers: list[list[Provider]] = metadata_providers or []
        self.constructor: Callable[..., Any] | None = None
        # Per-schema static reflection, computed once so the load hot path does not re-run
        # get_type_hints on every call (see coerce_flag_fields / compute_default_fallback_errors).
        self.flag_field_names: frozenset[str] = _compute_flag_field_names(schema)
        self.annotated_default_fields: tuple[tuple[str, list[Predicate]], ...] = _compute_annotated_default_fields(
            schema
        )

    @staticmethod
    def _base(rich: bool) -> Retort:  # noqa: FBT001
        return _BASE_RICH if rich else _BASE_FAST

    def _plain_key(
        self,
        source_idx: int,
        rich: bool,  # noqa: FBT001
        type_loaders: TypeLoaderMap | None,
    ) -> tuple[int, object, bool, frozenset[Any]]:
        return (source_idx, _PLAIN_SENTINEL, rich, _loaders_frozenset(type_loaders))

    def _field_pass_key(
        self,
        source_idx: int,
        skip: bool,  # noqa: FBT001
        rich: bool,  # noqa: FBT001
        type_loaders: TypeLoaderMap | None,
    ) -> tuple[int, object, bool, frozenset[Any]]:
        sentinel = _FIELD_PASS_SKIP_SENTINEL if skip else _FIELD_PASS_NOSKIP_SENTINEL
        return (source_idx, sentinel, rich, _loaders_frozenset(type_loaders))

    def _final_key(
        self,
        source_idx: int,
        rich: bool,  # noqa: FBT001
        type_loaders: TypeLoaderMap | None,
    ) -> tuple[int, object, bool, frozenset[Any]]:
        return (source_idx, _FINAL_SENTINEL, rich, _loaders_frozenset(type_loaders))

    def _get_or_build(self, key: tuple[Any, ...], build: Callable[[], Retort]) -> Retort:
        """Return ``self._cache[key]``, building it via *build* on a miss.

        When ``cache_engine`` is disabled, the result is never written to ``_cache`` — each call
        rebuilds from scratch and nothing compiled here outlives the call. This is the single
        chokepoint that makes retort caching opt-in.
        """
        if not self._cache_engine:
            return build()
        if key not in self._cache:
            self._cache[key] = build()
        return self._cache[key]

    def plain(
        self,
        indexed: IndexedSource,
        *,
        rich: bool = False,
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> Retort:
        """Return the plain loading retort for *indexed.source*, building and caching it on first call."""
        key = self._plain_key(indexed.index, rich, resolved_type_loaders)
        return self._get_or_build(
            key,
            lambda: self._base(rich).extend(
                recipe=build_base_recipe(indexed.source, resolved_type_loaders=resolved_type_loaders)
            ),
        )

    def _field_pass_raw(
        self,
        indexed: IndexedSource,
        *,
        skip: bool,
        rich: bool,
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> Retort:
        """Build (and cache) the raw field-pass ``Retort`` for the given *skip*/*rich* combination.

        Produces a ``dict`` keyed by field name, running on the source's own raw dict. Fields absent
        from the raw dict stay ``NOT_LOADED`` (``ModelToDictProvider``) so their validators do not
        fire. When *skip* is ``True`` (``source.skip_field_if_invalid``), ``SkipFieldProvider`` drops
        fields whose coercion *or validation* fails instead of raising.
        """

        def build() -> Retort:
            schema = self._schema
            skip_provider: list[Any] = [SkipFieldProvider()] if skip else []
            metadata_validator_providers = (
                self._metadata_providers[indexed.index] if indexed.index < len(self._metadata_providers) else []
            )
            # When skip=True (probe mode), ModelToDictProvider must apply to ALL nested
            # dataclasses so each nested field can be individually pruned.
            # When skip=False (validate mode), restrict to the top-level schema so that
            # validators on Annotated[NestedDC, V.check(...)] receive real instances.
            to_dict_provider = ModelToDictProvider() if skip else ModelToDictProvider(schema)
            return self.plain(indexed, rich=rich, resolved_type_loaders=resolved_type_loaders).extend(
                recipe=[
                    *skip_provider,
                    *get_validator_providers(schema),
                    *metadata_validator_providers,
                    to_dict_provider,
                ],
            )

        key = self._field_pass_key(indexed.index, skip, rich, resolved_type_loaders)
        return self._get_or_build(key, build)

    @overload
    def field_pass(
        self,
        indexed: IndexedSource,
        *,
        skip: Literal[True],
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> Retort: ...

    @overload
    def field_pass(
        self,
        indexed: IndexedSource,
        *,
        skip: Literal[False],
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> _DualRetort: ...

    def field_pass(
        self,
        indexed: IndexedSource,
        *,
        skip: bool,
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> Retort | _DualRetort:
        """Return the per-source field-validating loader (a ``dict`` keyed by field name).

        ``skip=False`` (validate mode) returns a fast/rich facade. ``skip=True`` (probe mode for
        ``skip_field_if_invalid``) returns a raw rich ``Retort``: that path uses load errors as
        per-field control flow, so replaying through a rich fallback on every skipped field would
        double the work — it stays on the trailed retort directly.
        """
        if skip:
            return self._field_pass_raw(indexed, skip=True, rich=True, resolved_type_loaders=resolved_type_loaders)
        fast = self._field_pass_raw(indexed, skip=False, rich=False, resolved_type_loaders=resolved_type_loaders)
        return _DualRetort(
            fast,
            lambda: self._field_pass_raw(indexed, skip=False, rich=True, resolved_type_loaders=resolved_type_loaders),
        )

    def prewarm(self, indexed: IndexedSource, *, resolved_type_loaders: TypeLoaderMap | None = None) -> None:
        """Force-compile the happy-path field-pass retorts so the first real load() is fast.

        Only the FAST variant is pre-warmed (the RICH fallback compiles lazily on first error).
        ``plain`` and ``final_retort`` are lazy — they compile on first use and are cached.
        """
        schema = self._schema
        if self.has_validators(indexed):
            self._field_pass_raw(
                indexed, skip=False, rich=False, resolved_type_loaders=resolved_type_loaders
            ).get_loader(schema)
        if indexed.source.skip_field_if_invalid:
            self._field_pass_raw(indexed, skip=True, rich=True, resolved_type_loaders=resolved_type_loaders).get_loader(
                schema
            )

    def _final_raw(
        self,
        indexed: IndexedSource,
        *,
        rich: bool,
        resolved_type_loaders: TypeLoaderMap | None = None,
    ) -> Retort:
        """Build (and cache) the raw final-construction ``Retort`` for the given *rich* variant."""

        def build() -> Retort:
            precomputed = (
                _uncustomized_fast_retort(indexed.source)
                if not rich
                and resolved_type_loaders is None
                and self.constructor is None
                and not self._root_providers
                and self._cache_engine
                else None
            )
            if precomputed is not None:
                return precomputed
            recipe = build_base_recipe(indexed.source, resolved_type_loaders=resolved_type_loaders)
            override = [ConstructorOverrideProvider(self.constructor, self._schema)] if self.constructor else []
            return self._base(rich).extend(recipe=[*recipe, *override, *self._root_providers])

        key = self._final_key(indexed.index, rich, resolved_type_loaders)
        return self._get_or_build(key, build)

    def final_retort(
        self, indexed: IndexedSource, *, resolved_type_loaders: TypeLoaderMap | None = None
    ) -> _DualRetort:
        """Return the final-construction loader as a fast/rich facade.

        Does type coercion + optional constructor override + root validators.
        In decorator mode (``self.constructor`` is set by ``_make_loader_subclass``), a
        ``ConstructorOverrideProvider`` is prepended so that adaptix calls the internal
        ``_dature_constructor`` instead of the raw schema constructor.
        In functional mode (``self.constructor`` is ``None``) adaptix uses the schema directly.
        Root validator providers always run at the end inside adaptix.
        """
        fast = self._final_raw(indexed, rich=False, resolved_type_loaders=resolved_type_loaders)
        return _DualRetort(
            fast,
            lambda: self._final_raw(indexed, rich=True, resolved_type_loaders=resolved_type_loaders),
        )

    def has_validators(self, indexed: IndexedSource) -> bool:
        """Return ``True`` when the source or schema has field validators requiring a ``field_pass``."""
        source = indexed.source
        return self._has_annotated_field_validators or bool(source.validators)
