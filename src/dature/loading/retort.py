import linecache
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import fields, is_dataclass
from enum import Flag
from typing import Any, Final, Literal, cast, get_type_hints, overload

from adaptix import Retort
from adaptix.provider import Provider

from dature.loading.default_factory import FactoryNode, unsafe_factory_tree
from dature.protocols import DataclassInstance
from dature.providers.compiler import generated_sources_var
from dature.providers.model import (
    ConstructorOverrideProvider,
    ModelToDictProvider,
    RequireUnsafeFactoryFieldsProvider,
)
from dature.providers.recipe import (
    BASE_FAST,
    BASE_RICH,
    build_base_recipe,
    uncustomized_fast_retort,
)
from dature.providers.skip import SkipFieldProvider
from dature.sources.base import IndexedSource
from dature.type_aliases import TypeLoaderMap
from dature.validators.base import create_root_validator_providers, extract_and_check_validators
from dature.validators.predicate import Predicate
from dature.validators.scan import scan_validators

_PLAIN_SENTINEL: Final[object] = object()
_FIELD_PASS_SKIP_SENTINEL: Final[object] = object()
_FIELD_PASS_NOSKIP_SENTINEL: Final[object] = object()
_FINAL_SENTINEL: Final[object] = object()


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


def _compute_unsafe_default_factory_fields[T](schema: type[T]) -> FactoryNode | None:
    """Return the tree of *schema* fields whose ``default_factory`` needs arguments, or ``None``.

    Pure static reflection — computed once per ``RetortCache`` so the load path pays only a
    single ``is None`` check on the overwhelmingly common schema with no such field. Used to
    enrich the "Missing required field" error such a field's absence now produces, via
    ``RequireUnsafeFactoryFieldsProvider``.
    """
    if not is_dataclass(schema):
        return None
    try:
        return unsafe_factory_tree(cast("type[DataclassInstance]", schema))
    except (NameError, TypeError, AttributeError):
        return None


def _compute_validator_scan[T](schema: type[T]) -> tuple[list[Provider], frozenset[type]]:
    """Return (validator providers, validator target types) for *schema*, in a single tree walk.

    ``get_validator_providers`` and ``validator_target_dataclass_types`` share the exact same
    schema walk; ``RetortCache`` needs both results, so it calls the combined ``scan_validators``
    once instead of walking the schema tree twice. Pure static reflection — computed once per
    ``RetortCache``. The target types are used by ``_field_pass_raw`` so ``ModelToDictProvider``
    converts every OTHER nested model to a dict (letting a section split across sources load
    field-by-field) while these types still receive real instances (so their validators can run).
    The schema's own type is always excluded from the target set: a self-referential schema's own
    top level must never be excluded from the field pass.

    Deliberately does not catch validator-declaration errors (e.g. ``V.root(...)`` placed in
    ``Annotated[...]`` metadata instead of ``root_validators=``) — those are meant to surface to
    the caller as a clear ``TypeError``, not be silently dropped.
    """
    if not is_dataclass(schema):
        return [], frozenset()
    providers, targets = scan_validators(cast("type[DataclassInstance]", schema))
    return providers, targets - {schema}


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
        self._validator_providers, self.validator_target_types = _compute_validator_scan(schema)
        self._has_annotated_field_validators: bool = bool(self._validator_providers)
        self._root_providers: list[Any] = create_root_validator_providers(schema, root_validators)
        self._metadata_providers: list[list[Provider]] = metadata_providers or []
        self.constructor: Callable[..., Any] | None = None
        # Per-schema static reflection, computed once so the load hot path does not re-run
        # get_type_hints on every call (see coerce_flag_fields / compute_default_fallback_errors /
        # compute_missing_factory_section_errors).
        self.flag_field_names: frozenset[str] = _compute_flag_field_names(schema)
        self.annotated_default_fields: tuple[tuple[str, list[Predicate]], ...] = _compute_annotated_default_fields(
            schema
        )
        self.unsafe_default_factory_fields: FactoryNode | None = _compute_unsafe_default_factory_fields(schema)

    @staticmethod
    def _base(rich: bool) -> Retort:  # noqa: FBT001
        return BASE_RICH if rich else BASE_FAST

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

    @contextmanager
    def evict_generated_sources(self) -> Iterator[None]:
        """Purge linecache entries this block causes adaptix to compile, when ``cache_engine`` is off.

        adaptix's ``BasicClosureCompiler._compile`` unconditionally writes the source of every
        compiled loader into the process-global ``linecache.cache`` for traceback readability,
        and never evicts it (see https://github.com/reagento/adaptix/issues/461). That's
        harmless when the compiled ``Retort`` is cached and reused, but with ``cache_engine``
        disabled a fresh ``Retort`` is compiled on every call (see ``_get_or_build``), so
        linecache would otherwise grow without bound.

        Every model-loader provider dature adds to a recipe (``TrackingModelLoaderProvider`` and
        the ``ModelLoaderProvider`` subclasses in ``dature.providers``) compiles through
        ``_TrackingCompiler``, which records each filename it registers into
        ``generated_sources_var`` while it's set. That lets this evict exactly what the current
        load compiled, rather than guessing by filename prefix — a concurrent load on another
        thread gets its own registry (``ContextVar`` is per-context) and is never touched. Nothing
        in adaptix itself is modified: each provider constructs its own ``_TrackingCompiler``
        instance via ``_get_compiler()``, a supported (if private) per-provider seam, so code
        elsewhere in the process using adaptix directly is unaffected.
        """
        if self._cache_engine:
            yield
            return
        registry: set[str] = set()
        token = generated_sources_var.set(registry)
        try:
            yield
        finally:
            generated_sources_var.reset(token)
            for key in registry:
                linecache.cache.pop(key, None)

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
            skip_provider: list[Any] = [SkipFieldProvider()] if skip else []
            metadata_validator_providers = (
                self._metadata_providers[indexed.index] if indexed.index < len(self._metadata_providers) else []
            )
            # When skip=True (probe mode), ModelToDictProvider must apply to ALL nested
            # dataclasses so each nested field can be individually pruned.
            # When skip=False (validate mode), exclude only the types a field validator is
            # directly attached to (self.validator_target_types) so Annotated[NestedDC, V.check(...)]
            # / Annotated[list[NestedDC], V.each(...)] still receive real instances. Every other
            # nested model becomes an optional-fields dict, so a section split across multiple
            # sources still loads field-by-field instead of requiring each source to be complete.
            to_dict_provider = (
                ModelToDictProvider() if skip else ModelToDictProvider(exclude=self.validator_target_types)
            )
            # RequireUnsafeFactoryFieldsProvider must sit AFTER to_dict_provider (lower priority):
            # it should only affect the types to_dict_provider declined (the validator-target
            # types still constructed for real), not ordinary sections converted to dicts —
            # otherwise it re-breaks loading a section split across multiple sources.
            unsafe_factory_provider: list[Any] = [] if skip else [RequireUnsafeFactoryFieldsProvider()]
            return self.plain(indexed, rich=rich, resolved_type_loaders=resolved_type_loaders).extend(
                recipe=[
                    *skip_provider,
                    *self._validator_providers,
                    *metadata_validator_providers,
                    to_dict_provider,
                    *unsafe_factory_provider,
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
                uncustomized_fast_retort(indexed.source)
                if not rich
                and resolved_type_loaders is None
                and self.constructor is None
                and not self._root_providers
                and self.unsafe_default_factory_fields is None
                and self._cache_engine
                else None
            )
            if precomputed is not None:
                return precomputed
            override = [ConstructorOverrideProvider(self.constructor, self._schema)] if self.constructor else []
            unsafe_factory_override = [RequireUnsafeFactoryFieldsProvider()]
            recipe = build_base_recipe(indexed.source, resolved_type_loaders=resolved_type_loaders)
            return self._base(rich).extend(recipe=[*recipe, *unsafe_factory_override, *override, *self._root_providers])

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
