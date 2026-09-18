"""Public ``Loader`` class.

A ``Loader`` captures everything a ``load(...)`` call would: the sources, the
schema, all load-level parameters, and an optional cache (eternal, TTL, or
disabled). Calling ``loader.load()`` returns the parsed dataclass instance,
hitting the cache when fresh and re-loading otherwise.

The class is the public entry point for advanced control flows — caching across
repeated calls, TTL-based invalidation, and (in the future) polling/watchers.
``dature.load(...)`` is a thin shortcut that constructs a throwaway ``Loader``
and calls ``.load()`` once; no cache state survives that call. To make caching
useful in function mode, keep the ``Loader`` instance and invoke ``.load()``
multiple times.

The decorator form (`` @dature.load(...) `` or ``Loader.as_decorator(...)``)
creates a single ``Loader`` per class and returns a subclass whose ``__init__``
delegates to ``loader.load()``.  The original dataclass is never modified.
"""

import logging
import threading
import warnings
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import timedelta
from functools import update_wrapper
from typing import Any, NoReturn, cast

from adaptix import Retort

from dature._deprecations import SEARCH_SYSTEM_PATHS_MESSAGE
from dature.config import DatureConfig, default_config
from dature.errors import DatureConfigError, DatureError, DatureErrorGroup
from dature.errors.extraction import handle_load_errors
from dature.errors.location import ErrorContext
from dature.errors.truncation import raise_truncated
from dature.loading.cache import aligned_now, cache_is_fresh
from dature.loading.context import coerce_flag_fields, merge_fields
from dature.loading.cross_source import clone_with_interpolation, evaluate_when_eager, when_has_cross_refs
from dature.loading.field_pass import build_revalidation
from dature.loading.mask_config import apply_masking_mode
from dature.loading.merge import load_and_merge, load_single
from dature.loading.merge_runtime import (
    MergeConfig,
    SourceMergeStrategy,
    SourceParams,
    resolve_type_loaders,
)
from dature.loading.retort import RetortCache
from dature.loading.source_validation import validate_source
from dature.masking.detection import build_secret_paths
from dature.protocols import DataclassInstance
from dature.reloading.controller import ReloadController, ReloadOutcome, validate_reload_args
from dature.reloading.protocol import ReloadTriggerProtocol
from dature.report import attach_load_report, load_report
from dature.sources.base import IndexedSource
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import (
    ConfigDirsArg,
    ExpandEnvVarsMode,
    FieldGroupTuple,
    FieldMergeMap,
    JSONValue,
    MaskingMode,
    MergeStrategyName,
    NestedResolve,
    NestedResolveStrategy,
    ReloadCallback,
    ReloadErrorCallback,
    SkipFieldsInvalid,
    StaleOnErrorMode,
    StrictMode,
    TypeLoaderMap,
)
from dature.validators.base import create_metadata_validator_providers
from dature.validators.root import RootPredicate

logger = logging.getLogger("dature")


@dataclass(frozen=True, slots=True)
class _CacheEntry[T]:
    """Immutable cache snapshot. Published/read as a single attribute for lock-free reads."""

    data: T
    at: float


def _fold_search_system_paths(
    *,
    search_system_paths: bool | None,
    config_dirs: "ConfigDirsArg | None",
) -> "ConfigDirsArg | None":
    """Fold the deprecated ``search_system_paths`` flag into ``config_dirs``. Removed in 1.6."""
    if search_system_paths is None:
        return config_dirs
    warnings.warn(SEARCH_SYSTEM_PATHS_MESSAGE, DeprecationWarning, stacklevel=3)
    if search_system_paths is False and config_dirs is None:
        return ()
    return config_dirs


def _validate_sources(sources: tuple[SourceProtocol, ...]) -> None:
    if not sources:
        msg = "Loader requires at least one Source"
        raise TypeError(msg)
    for s in sources:
        if not isinstance(s, SourceProtocol):
            msg = f"Loader positional arguments must be SourceProtocol instances, got {s!r}"
            raise TypeError(msg)


class Loader[T: DataclassInstance]:
    """Encapsulates a ``load`` call. ``.load()`` honours the cache."""

    def __init__(  # noqa: PLR0913, PLR0915
        self,
        *sources: SourceProtocol,
        schema: type[T],
        cache: bool | timedelta | None = None,
        cache_engine: bool | None = None,
        stale_on_error: StaleOnErrorMode | None = None,
        debug: bool | None = None,
        strict: StrictMode | None = None,
        strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
        field_merges: FieldMergeMap | None = None,
        field_groups: Sequence[FieldGroupTuple] = (),
        root_validators: Iterable[RootPredicate] = (),
        skip_if_broken: bool = False,
        skip_if_missing: bool = False,
        skip_field_if_invalid: SkipFieldsInvalid = None,
        expand_env_vars: ExpandEnvVarsMode | None = None,
        secret_field_names: Sequence[str] | None = None,
        masking_mode: MaskingMode | None = None,
        type_loaders: TypeLoaderMap | None = None,
        nested_resolve_strategy: NestedResolveStrategy | None = None,
        nested_resolve: NestedResolve | None = None,
        config_dirs: ConfigDirsArg | None = None,
        search_system_paths: bool | None = None,  # deprecated — removed in dature 1.6
        reload: ReloadTriggerProtocol | None = None,
        on_reload: ReloadCallback[T] | None = None,
        on_error: ReloadErrorCallback | None = None,
        config: DatureConfig | None = None,
    ) -> None:
        _validate_sources(sources)
        config_dirs = _fold_search_system_paths(
            search_system_paths=search_system_paths,
            config_dirs=config_dirs,
        )

        self._config: DatureConfig = apply_masking_mode(
            config if config is not None else default_config(), masking_mode=masking_mode
        )

        if cache is None:
            cache = self._config.loading.cache
        if isinstance(cache, timedelta) and cache < timedelta(0):
            msg = f"cache timedelta must be non-negative, got {cache!r}"
            raise ValueError(msg)
        validate_reload_args(
            schema_name=schema.__name__,
            cache=cache,
            reload=reload,
            on_reload=on_reload,
            on_error=on_error,
        )
        if cache_engine is None:
            cache_engine = self._config.loading.cache_engine
        if stale_on_error is None:
            stale_on_error = self._config.loading.stale_on_error
        if debug is None:
            debug = self._config.loading.debug
        if strict is None:
            strict = self._config.loading.strict

        # All raw sources as passed — eager when= filter runs at .load() time so that
        # env state is read at invocation time, not at import/construction time.
        # This fixes the decorator-mode footgun where APP_ENV unset at import causes failure.
        self._sources = sources
        self._schema = schema
        self._cache: bool | timedelta = cache
        self._cache_engine: bool = cache_engine
        self._stale_on_error: StaleOnErrorMode = stale_on_error
        self.debug = debug
        self._strict: StrictMode = strict

        # Loader-level parameters stored for deferred MergeConfig construction in _prepare_for_load.
        self._strategy: MergeStrategyName | SourceMergeStrategy = strategy
        self._field_merges = field_merges
        self._field_groups = field_groups
        self._skip_if_broken = skip_if_broken
        self._skip_if_missing = skip_if_missing
        self._skip_field_if_invalid = skip_field_if_invalid
        self._secret_field_names = secret_field_names
        self._type_loaders_arg: TypeLoaderMap | None = type_loaders
        self._source_params = SourceParams(
            expand_env_vars=expand_env_vars,
            nested_resolve_strategy=nested_resolve_strategy,
            nested_resolve=nested_resolve,
            strict=strict,
            config_dirs=config_dirs,
        )

        self.field_list = fields(schema)

        # Cache state — published/read as one atomic snapshot so the hot read path never
        # needs a lock (see _CacheEntry).
        self._cache_entry: _CacheEntry[T] | None = None
        self._lock = threading.RLock()

        # reload= is an external cache-invalidation signal: its trigger writes into the same
        # _cache_entry that the TTL/eternal cache reads from. See ReloadController for the
        # lifecycle (weakref safety net, start/stop idempotency, on_reload/on_error dispatch).
        self._reload: ReloadController[T] | None = (
            ReloadController(
                self,
                trigger=reload,
                on_reload=on_reload,
                on_error=on_error,
                schema_name=schema.__name__,
            )
            if reload is not None
            else None
        )

        # Tracks which source indices were enabled on the last load.
        # When the enabled set changes (env var drove a different when= outcome),
        # the cached result is auto-cleared before the freshness check.
        # If no source has when=, the enabled set is fixed at construction time and never recomputed.
        self._has_conditional_sources: bool = any(s.when is not None for s in sources)
        self._enabled_sig: tuple[int, ...] | None = (
            None if self._has_conditional_sources else tuple(range(len(sources)))
        )

        # Secret paths depend only on schema shape — computed once, env-free.
        self.secret_paths: frozenset[str] = frozenset()
        if self._config.masking.masking_mode != "none":
            extra_patterns = tuple(secret_field_names) if secret_field_names else ()
            self.secret_paths = build_secret_paths(
                schema,
                base_patterns=self._config.masking.secret_field_names,
                extra_patterns=extra_patterns,
                field_mappings=tuple(s.field_mapping for s in sources),
            )

        metadata_providers = [create_metadata_validator_providers(source.validators or {}) for source in sources]
        # Build the shared retort cache for this Loader. All retorts are owned here, not
        # on Source — Source is a pure config DTO. Per-source retorts are keyed by the
        # source's positional index so that clones produced during load() share the entry
        # pre-warmed here against the original source object.
        # ``cache_engine`` controls whether RetortCache retains what it builds: with it off,
        # nothing compiled here (or later, during load()) stays reachable past its use, which
        # is what keeps the decorator's retained memory down when `cache=True` already avoids
        # ever needing it again.
        self._retort_cache = RetortCache(
            schema,
            root_validators=root_validators,
            cache_engine=cache_engine,
            metadata_providers=metadata_providers,
        )

        # Pre-warm retorts for all sources (pure type analysis, no env read). Only worth doing
        # eagerly when the result is actually retained — otherwise it's compiled for nothing
        # since it won't survive past this call anyway.
        if cache_engine:
            self._prewarm_sources(sources, type_loaders)

        # Runtime state set by _prepare_for_load on each .load() call.
        self._merge_meta: MergeConfig | None = None
        self._is_single: bool = False
        self._source: SourceProtocol | None = None
        self._type_loaders: TypeLoaderMap | None = None
        self._probe_retort: Retort | None = None

        self.validation_loader: Callable[[JSONValue], DataclassInstance] | None = None
        self.error_ctx: ErrorContext | None = None
        self._revalidation_indexed: IndexedSource | None = None

    def _prewarm_sources(self, sources: tuple[SourceProtocol, ...], type_loaders: TypeLoaderMap | None) -> None:
        for source_idx, source in enumerate(sources):
            indexed = IndexedSource(source, source_idx)
            source_type_loaders = resolve_type_loaders(source, type_loaders)
            self._retort_cache.prewarm(indexed, resolved_type_loaders=source_type_loaders)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def load(self) -> T:
        """Load and return the parsed config instance.

        ``when=`` conditions are evaluated on every call so env-var changes
        take effect immediately.  The cache is cleared automatically when
        the set of enabled sources changes between calls.
        """
        # Re-evaluate when= routing fresh on every call only when sources may be conditional.
        # When no source has when=, the enabled set is fixed and _enabled_sig is pre-set at
        # construction time — skipping this loop is the fast path for the common case.
        if self._has_conditional_sources:
            with self._lock:
                self._refresh_enabled_sig_locked()

        # Single atomic attribute read — safe without the lock even while a background
        # reload is concurrently publishing a new entry (see _CacheEntry).
        entry = self._cache_entry
        if entry is not None and cache_is_fresh(cache=self._cache, cached_at=entry.at):
            return entry.data

        with self._lock:
            result, _ = self._load_locked(force=False)
            return result

    def _refresh_enabled_sig_locked(self) -> None:
        new_sig = tuple(i for i, s in enumerate(self._sources) if when_has_cross_refs(s) or evaluate_when_eager(s.when))
        if new_sig != self._enabled_sig:
            self._cache_entry = None
            self._enabled_sig = new_sig
            self._merge_meta = None
            self._source = None

    def _load_locked(self, *, force: bool) -> tuple[T, Exception | None]:
        """Perform (or skip) a full load. Must be called with ``self._lock`` held.

        ``force=False`` re-checks freshness first — another thread may have already
        refreshed the entry while this one was waiting for the lock. The second element of
        the return value is the exception that forced a stale fallback, or ``None`` on a
        normal load — only the trigger-driven reload path needs it (to report it to
        ``on_error``); ``load()`` discards it.
        """
        if not force:
            entry = self._cache_entry
            if entry is not None and cache_is_fresh(cache=self._cache, cached_at=entry.at):
                return entry.data, None
        try:
            if self._merge_meta is None:
                self._prepare_for_load()
            result = self._do_load()
        except (DatureError, DatureErrorGroup, DatureConfigError) as exc:
            stale = self._stale_fallback(exc)
            if stale is None:
                self._raise_or_truncate(exc)
            return stale, exc
        except Exception as exc:  # noqa: BLE001
            exc.__traceback__ = None  # sub-exceptions in ExceptionGroup render their own tb even when outer tb=None
            stale = self._stale_fallback(exc)
            if stale is None:
                raise DatureConfigError(self._schema.__name__, [exc]) from None  # pyright: ignore[reportArgumentType]
            return stale, exc
        if self._cache is not False:
            self._cache_entry = _CacheEntry(result, aligned_now(self._cache))
        self.start_reload()
        return result, None

    def _refresh_locked(self) -> tuple[T, Exception | None]:
        """Force a full reload, bypassing freshness. Must be called with ``self._lock`` held."""
        if self._has_conditional_sources:
            self._refresh_enabled_sig_locked()
        self._merge_meta = None
        self._source = None
        return self._load_locked(force=True)

    def _raise_or_truncate(self, exc: DatureError | DatureErrorGroup | DatureConfigError) -> NoReturn:
        """Re-raise *exc*, truncating it first if it's a group that exceeds ``max_errors``.

        Split out of ``load()``'s except clause purely to keep that method's branching
        under the complexity threshold; ``exc`` is still the exception being handled here,
        so both ``raise_truncated`` and the bare ``raise`` preserve the original traceback.
        """
        if isinstance(exc, DatureErrorGroup):
            raise_truncated(exc, self._config.error_display)
        raise exc

    def _revalidate(self, instance: Any) -> None:  # noqa: ANN401
        """Re-run validation on *instance* after decorator-mode caller overrides are merged in.

        No-op unless the schema actually needs revalidation (``_ensure_revalidation`` decides
        that once and caches it). Split out of ``_dature_init`` purely to keep that closure's
        branching under the complexity threshold.
        """
        self._ensure_revalidation()
        validation_loader = self.validation_loader
        error_ctx = self.error_ctx
        if validation_loader is None or error_ctx is None:
            return
        obj_dict = coerce_flag_fields(asdict(instance), self._retort_cache.flag_field_names)
        try:
            handle_load_errors(func=lambda: validation_loader(obj_dict), ctx=error_ctx)
        except DatureErrorGroup as exc:
            raise_truncated(exc, self._config.error_display)

    def _stale_fallback(self, exc: Exception) -> T | None:
        """Return the previously cached config after a load failure, or ``None`` if *exc* must
        propagate instead (per ``stale_on_error``, or because there's nothing to fall back to).

        There is nothing to fall back to on the very first load — ``_cache_entry`` is only ever
        populated by a prior successful ``.load()``. ``"keep"`` restarts the TTL window on the
        stale value so a persistently broken source isn't retried on every access; ``"retry"``
        leaves ``at`` untouched so the next call attempts a fresh reload again.
        """
        entry = self._cache_entry
        if entry is None:
            return None
        match self._stale_on_error:
            case "raise":
                return None
            case "keep":
                entry = _CacheEntry(entry.data, aligned_now(self._cache))
                self._cache_entry = entry
            case "retry":
                pass
            case _ as unknown:
                msg = f"Unknown stale_on_error mode: {unknown!r}"
                raise ValueError(msg) from None
        logger.warning(
            "[%s] Config reload failed, keeping the previously loaded config: %s",
            self._schema.__name__,
            exc,
        )
        return entry.data

    # ------------------------------------------------------------------ #
    # Background reload
    # ------------------------------------------------------------------ #

    def start_reload(self) -> None:
        """Start the background reload trigger. Idempotent. No-op if ``reload=`` wasn't passed."""
        if self._reload is not None:
            self._reload.start(self._sources)

    def stop_reload(self) -> None:
        """Stop the background reload trigger. Idempotent, safe even if never started."""
        if self._reload is not None:
            self._reload.stop()

    def _reload_for_trigger(self) -> ReloadOutcome[T]:
        """Force a full reload for the trigger. Runs on the shared scheduler thread.

        This is ``Loader``'s implementation of ``ReloadTarget`` — called by ``ReloadController``
        from the trigger's thread, wrapped in a weakref check that never lets an exception
        escape to that thread.
        """
        with self._lock:
            previous = self._cache_entry
            instance, stale_exc = self._refresh_locked()
        changed = previous is None or instance is not previous.data
        return ReloadOutcome(instance=instance, error=stale_exc, changed=changed)

    @staticmethod
    def as_decorator[DC: DataclassInstance](  # noqa: PLR0913
        *sources: SourceProtocol,
        cache: bool | timedelta | None = None,
        cache_engine: bool | None = None,
        stale_on_error: StaleOnErrorMode | None = None,
        debug: bool | None = None,
        strict: StrictMode | None = None,
        strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
        field_merges: FieldMergeMap | None = None,
        field_groups: Sequence[FieldGroupTuple] = (),
        root_validators: Iterable[RootPredicate] = (),
        skip_if_broken: bool = False,
        skip_if_missing: bool = False,
        skip_field_if_invalid: SkipFieldsInvalid = None,
        expand_env_vars: ExpandEnvVarsMode | None = None,
        secret_field_names: Sequence[str] | None = None,
        masking_mode: MaskingMode | None = None,
        type_loaders: TypeLoaderMap | None = None,
        nested_resolve_strategy: NestedResolveStrategy | None = None,
        nested_resolve: NestedResolve | None = None,
        config_dirs: ConfigDirsArg | None = None,
        search_system_paths: bool | None = None,  # deprecated — removed in dature 1.6
        reload: ReloadTriggerProtocol | None = None,
        on_reload: ReloadCallback[DataclassInstance] | None = None,
        on_error: ReloadErrorCallback | None = None,
        config: DatureConfig | None = None,
    ) -> Callable[[type[DC]], type[DC]]:
        """Return a decorator that creates a loading subclass for the target dataclass."""

        def decorator(target_cls: type[DC]) -> type[DC]:
            if not is_dataclass(target_cls):
                msg = f"{target_cls.__name__} must be a dataclass"
                raise TypeError(msg)

            loader = Loader(
                *sources,
                schema=target_cls,
                cache=cache,
                cache_engine=cache_engine,
                stale_on_error=stale_on_error,
                debug=debug,
                strict=strict,
                strategy=strategy,
                field_merges=field_merges,
                field_groups=field_groups,
                root_validators=root_validators,
                skip_if_broken=skip_if_broken,
                skip_if_missing=skip_if_missing,
                skip_field_if_invalid=skip_field_if_invalid,
                expand_env_vars=expand_env_vars,
                secret_field_names=secret_field_names,
                masking_mode=masking_mode,
                type_loaders=type_loaders,
                nested_resolve_strategy=nested_resolve_strategy,
                nested_resolve=nested_resolve,
                config_dirs=config_dirs,
                search_system_paths=search_system_paths,
                reload=reload,
                on_reload=on_reload,
                on_error=on_error,
                config=config,
            )
            return loader._make_loader_subclass(target_cls)

        return decorator

    # ------------------------------------------------------------------ #
    # Internal — used by the decorator's loading subclass.
    # ------------------------------------------------------------------ #

    # ``validation_loader`` and ``error_ctx`` are set after each ``load()``
    # call by ``build_revalidation`` and read by the subclass ``__post_init__``
    # for re-validation of explicit-kwarg construction.

    @property
    def source(self) -> SourceProtocol:
        """Single-source mode: the prepared source after default resolution."""
        if self._source is None:
            msg = "Loader.source is only available in single-source mode"
            raise AttributeError(msg)
        return self._source

    @property
    def type_loaders(self) -> TypeLoaderMap | None:
        return self._type_loaders

    @property
    def probe_retort(self) -> Retort | None:
        return self._probe_retort

    # ------------------------------------------------------------------ #
    # Loading machinery
    # ------------------------------------------------------------------ #

    def _prepare_for_load(self) -> None:
        """Build env-dependent runtime state: filter when=, construct MergeConfig.

        Called at the start of every .load() so that env vars are read at
        invocation time, not at import/construction time (decorator-mode fix).
        Invalidates the previous _merge_meta on each call so stale state from a
        prior cache miss does not bleed into the next invocation.
        """
        enabled = tuple(s for s in self._sources if when_has_cross_refs(s) or evaluate_when_eager(s.when))
        if not enabled:
            msg = "Loader requires at least one enabled Source (all sources filtered out by when=)"
            raise DatureConfigError(self._schema.__name__, [DatureError(msg)])

        self._is_single = len(enabled) == 1

        # Always build MergeConfig — it runs prepare_sources + build_cross_ref_plan
        # (collision detection) on the enabled set. Single-source re-uses the same
        # path, eliminating the separate prepare_single_source code path.
        self._merge_meta = MergeConfig(
            sources=enabled,
            source_params=self._source_params,
            strategy=self._strategy,
            field_merges=self._field_merges,
            field_groups=self._field_groups,
            skip_if_broken=self._skip_if_broken,
            skip_if_missing=self._skip_if_missing,
            skip_field_if_invalid=self._skip_field_if_invalid,
            secret_field_names=self._secret_field_names,
            type_loaders=self._type_loaders_arg,
            config=self._config,
        )

        if self._is_single:
            source = self._merge_meta.sources[0]
            # Apply $$ → $ escaping. Multi-mode does this inside LoadCtx._prepare_source
            # where each source's context is already available; for single-mode there are
            # no cross-ref deps, so we can run it with an empty context immediately.
            source = clone_with_interpolation(source, {})
            validate_source(source)
            self._merge_meta.sources = (source,)
            self._source = source
            self._type_loaders = resolve_type_loaders(source, self._type_loaders_arg)
            self._probe_retort = (
                self._retort_cache.field_pass(
                    IndexedSource(source, 0), skip=True, resolved_type_loaders=self._type_loaders
                )
                if source.skip_field_if_invalid
                else None
            )

    def _do_load(self) -> T:
        # Reset lazy re-validation state so a prior load's loader/ctx can't leak into this one
        # (relevant when conditional sources flip the enabled set between single- and multi-mode).
        self.validation_loader = None
        self.error_ctx = None
        self._revalidation_indexed = None
        if self._is_single:
            return self._do_load_single()
        return self._do_load_multi()

    def _do_load_single(self) -> T:
        indexed = IndexedSource(self._source, 0)  # type: ignore[arg-type]  # set by _prepare_for_load
        data = load_single(
            indexed=indexed,
            schema=self._schema,
            retort_cache=self._retort_cache,
            type_loaders=self._type_loaders_arg,
            secret_paths=self.secret_paths,
            probe_retort=self._probe_retort,
            debug=self.debug,
            masking=self._config.masking,
            error_display=self._config.error_display,
        )
        # Single-source uses the load's own error_ctx (it may carry nested-conflict detail that a
        # freshly built ctx would lack); the validation_loader itself is built lazily on demand.
        self._revalidation_indexed = indexed
        self.error_ctx = data.error_ctx
        return data.result

    def _do_load_multi(self) -> T:
        data = load_and_merge(
            merge_meta=self._merge_meta,  # type: ignore[arg-type]  # set by _prepare_for_load
            schema=self._schema,
            retort_cache=self._retort_cache,
            debug=self.debug,
            secret_paths=self.secret_paths,
        )
        self._revalidation_indexed = data.last_loaded
        return data.result

    def _ensure_revalidation(self) -> None:
        """Build the decorator-mode ``(validation_loader, error_ctx)`` pair on first slow-path use.

        Invoked only from the decorator subclass ``__init__`` when the caller passed explicit
        overrides. Reuses the ``IndexedSource`` captured by the last ``load()``; runs synchronously
        right after that load, so multi-mode ``last_loaded`` is still current.
        """
        if self.validation_loader is not None or self._revalidation_indexed is None:
            return
        validation_loader, ctx = build_revalidation(
            indexed=self._revalidation_indexed,
            schema=self._schema,
            retort_cache=self._retort_cache,
            type_loaders=self._type_loaders_arg,
            secret_paths=self.secret_paths,
            masking=self._config.masking,
            error_display=self._config.error_display,
        )
        self.validation_loader = validation_loader
        # Single-source set error_ctx eagerly (richer ctx); multi-source takes build_revalidation's.
        if self.error_ctx is None:
            self.error_ctx = ctx

    def _make_loader_subclass(self, target_cls: type[T]) -> type[T]:
        """Return a subclass of *target_cls* that auto-loads on every ``__init__`` call.

        The original class is never modified.  ``_dature_skip=True`` is used internally
        to construct instances without triggering the load path.
        """
        original_init: Callable[..., None] = target_cls.__init__
        original_post_init: Callable[..., None] | None = getattr(target_cls, "__post_init__", None)
        field_list = fields(target_cls)
        loader = self

        def _dature_init(self: Any, *args: Any, _dature_skip: bool = False, **kwargs: Any) -> None:  # noqa: ANN401
            if _dature_skip:
                # Internal path: data is already coerced; just initialise fields.
                # original_init will call self.__post_init__() → class_body's no-op.
                original_init(self, **kwargs)
                return

            loaded_data = loader.load()

            if not args and not kwargs:
                # Fast path: no caller overrides — loaded_data already validated by the load
                # pipeline, so merge and revalidation are both unnecessary.
                original_init(self, **{f.name: getattr(loaded_data, f.name) for f in field_list})
                if loader.debug:
                    _attach_debug_report(self, loaded_data)
                if original_post_init is not None:
                    original_post_init(self)
                return

            # Slow path: explicit overrides — merge caller values, then revalidate the result.
            complete_kwargs = merge_fields(loaded_data, field_list, args, kwargs)
            original_init(self, **complete_kwargs)
            if loader.debug:
                _attach_debug_report(self, loaded_data)
            if original_post_init is not None:
                original_post_init(self)
            loader._revalidate(self)

        # update_wrapper sets __wrapped__ so inspect.signature follows through to the
        # original signature, and copies __name__/__qualname__/__doc__/__annotations__.
        update_wrapper(_dature_init, target_cls.__init__)

        class_body: dict[str, Any] = {"__init__": _dature_init}
        if original_post_init is not None:
            # Intercept the __post_init__ call that original_init emits so the user's
            # method is not called on every internal construction.  We call it explicitly
            # from _dature_init on the user path only.
            class_body["__post_init__"] = lambda self: None  # noqa: ARG005

        _subclass: type[T] = cast("type[T]", type(target_cls.__name__, (target_cls,), class_body))
        _subclass.__qualname__ = target_cls.__qualname__
        _subclass.__module__ = target_cls.__module__

        self._retort_cache.constructor = lambda **kw: _subclass(_dature_skip=True, **kw)  # type: ignore[call-arg]
        return _subclass


def _attach_debug_report(instance: DataclassInstance, loaded_data: DataclassInstance) -> None:
    """Attach a ``LoadReport`` to ``instance`` after a decorator-driven construction."""
    report = load_report(loaded_data)
    if report is not None:
        attach_load_report(instance, report)
