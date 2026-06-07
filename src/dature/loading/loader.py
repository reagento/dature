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
creates a single ``Loader`` per class and routes every ``Cls()`` invocation
through ``loader.load()`` via a patched ``__init__``.
"""

import logging
from collections.abc import Callable
from dataclasses import fields, is_dataclass
from datetime import timedelta
from typing import Any

from adaptix import Retort

from dature.config import config
from dature.errors import DatureConfigError, DatureError, DatureErrorGroup
from dature.errors.formatter import handle_load_errors
from dature.errors.location import ErrorContext, SkippedFieldSource, read_file_content
from dature.load_report import (
    LoadReport,
    _build_single_source_report,
    attach_load_report,
    get_load_report,
)
from dature.loading.cache import _aligned_now, cache_is_fresh
from dature.loading.common import resolve_mask_secrets
from dature.loading.context import (
    apply_skip_invalid,
    build_error_ctx,
    coerce_flag_fields,
    make_validating_post_init,
    merge_fields,
)
from dature.loading.cross_source import clone_with_interpolation, evaluate_when_eager, when_has_cross_refs
from dature.loading.merge import _MergedData, load_and_merge
from dature.loading.merge_runtime import (
    MergeConfig,
    SourceMergeStrategy,
    SourceParams,
    resolve_type_loaders,
)
from dature.loading.source_loading import enrich_skipped_errors
from dature.masking.detection import build_secret_paths
from dature.masking.masking import mask_json_value
from dature.protocols import DataclassInstance
from dature.sources.base import Source
from dature.sources.retort import (
    build_base_recipe,
    create_probe_retort,
    create_validating_retort,
    ensure_retort,
    probe_retort_key,
    transform_to_dataclass,
    validating_retort_key,
)
from dature.types import (
    ExpandEnvVarsMode,
    FieldGroupTuple,
    FieldMergeMap,
    JSONValue,
    MergeStrategyName,
    NestedResolve,
    NestedResolveStrategy,
    TypeLoaderMap,
)

logger = logging.getLogger("dature")


def _log_single_source_load(
    *,
    dataclass_name: str,
    loader_type: str,
    file_path: str,
    data: JSONValue,
    secret_paths: frozenset[str] = frozenset(),
) -> None:
    logger.debug(
        "[%s] Single-source load: loader=%s, file=%s",
        dataclass_name,
        loader_type,
        file_path,
    )
    if secret_paths:
        masked_data = mask_json_value(data, secret_paths=secret_paths)
    else:
        masked_data = data
    logger.debug(
        "[%s] Loaded data: %s",
        dataclass_name,
        masked_data,
    )


class Loader[T: DataclassInstance]:
    """Encapsulates a ``load`` call. ``.load()`` honours the cache."""

    def __init__(  # noqa: PLR0913, PLR0915, C901
        self,
        *sources: Source,
        schema: type[T],
        cache: bool | timedelta | None = None,
        debug: bool | None = None,
        strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
        field_merges: FieldMergeMap | None = None,
        field_groups: tuple[FieldGroupTuple, ...] = (),
        skip_broken_sources: bool = False,
        skip_invalid_fields: bool = False,
        expand_env_vars: ExpandEnvVarsMode | None = None,
        secret_field_names: tuple[str, ...] | None = None,
        mask_secrets: bool | None = None,
        type_loaders: TypeLoaderMap | None = None,
        nested_resolve_strategy: NestedResolveStrategy | None = None,
        nested_resolve: NestedResolve | None = None,
    ) -> None:
        if not sources:
            msg = "Loader requires at least one Source"
            raise TypeError(msg)
        for s in sources:
            if not isinstance(s, Source):
                msg = f"Loader positional arguments must be Source instances, got {s!r}"
                raise TypeError(msg)

        if cache is None:
            cache = config.loading.cache
        if isinstance(cache, timedelta) and cache < timedelta(0):
            msg = f"cache timedelta must be non-negative, got {cache!r}"
            raise ValueError(msg)
        if debug is None:
            debug = config.loading.debug

        # All raw sources as passed — eager when= filter runs at .load() time so that
        # env state is read at invocation time, not at import/construction time.
        # This fixes the decorator-mode footgun where APP_ENV unset at import causes failure.
        self._sources = sources
        self._schema = schema
        self._cache: bool | timedelta = cache
        self.debug = debug

        # Loader-level parameters stored for deferred MergeConfig construction in _prepare_for_load.
        self._strategy = strategy
        self._field_merges = field_merges
        self._field_groups = field_groups
        self._skip_broken_sources = skip_broken_sources
        self._skip_invalid_fields = skip_invalid_fields
        self._secret_field_names = secret_field_names
        self._mask_secrets_arg = mask_secrets
        self._type_loaders_arg = type_loaders
        self._source_params = SourceParams(
            expand_env_vars=expand_env_vars,
            nested_resolve_strategy=nested_resolve_strategy,
            nested_resolve=nested_resolve,
        )

        # State exposed to the decorator's patched __init__ / __post_init__
        # (satisfies the PatchContext protocol from ``loading.context``).
        self.cls: type[T] = schema
        self.field_list = fields(schema)
        self.original_init = schema.__init__
        self.original_post_init = getattr(schema, "__post_init__", None)
        self.loading = False
        self.validating = False

        # Cache state.
        self._cached_data: T | None = None
        self._cached_at: float | None = None
        # Tracks which source indices were enabled on the last load.
        # When the enabled set changes (env var drove a different when= outcome),
        # the cached result is auto-cleared before the freshness check.
        self._enabled_sig: tuple[int, ...] | None = None

        # Secret paths depend only on schema shape — computed once, env-free.
        resolved_mask_secrets = resolve_mask_secrets(load_level=mask_secrets)
        self.secret_paths: frozenset[str] = frozenset()
        if resolved_mask_secrets:
            extra_patterns = secret_field_names or ()
            self.secret_paths = build_secret_paths(schema, extra_patterns=extra_patterns)

        # Pre-warm retort caches for all sources (pure type analysis, no env read).
        # Must happen before the decorator replaces schema.__init__ so that adaptix
        # inspects the original dataclass signature, not the patched *args/**kwargs one.
        # Retorts are stored in source.retorts (per-instance dict) using sentinel keys so
        # that two sources of the same type with different configs never share a retort.
        # clone_source does copy.copy → clone.retorts is source.retorts, so pre-warmed
        # retorts are visible on clones without any extra work.
        for source in sources:
            source_type_loaders = resolve_type_loaders(source, type_loaders)
            base_recipe = build_base_recipe(source, resolved_type_loaders=source_type_loaders)
            ensure_retort(source, schema, base_recipe, resolved_type_loaders=source_type_loaders)
            v_key = validating_retort_key(source_type_loaders)
            if v_key not in source.retorts:
                validating_retort = create_validating_retort(source, schema, base_recipe)
                validating_retort.get_loader(schema)
                source.retorts[v_key] = validating_retort
            if source.skip_field_if_invalid:
                p_key = probe_retort_key(source_type_loaders)
                if p_key not in source.retorts:
                    probe_retort = create_probe_retort(base_recipe)
                    probe_retort.get_loader(schema)
                    source.retorts[p_key] = probe_retort

        # Runtime state set by _prepare_for_load on each .load() call.
        self._merge_meta: MergeConfig | None = None
        self._is_single: bool = False
        self._source: Source | None = None
        self._type_loaders: TypeLoaderMap | None = None
        self._probe_retort: Retort | None = None

        # Set by _build_validation_loader; exposed for decorator-protocol consumers.
        self.validation_loader: Callable[[JSONValue], DataclassInstance] | None = None
        self.error_ctx: ErrorContext | None = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def load(self) -> T:
        """Load and return the parsed config instance.

        ``when=`` conditions are evaluated on every call so env-var changes
        take effect immediately.  The cache is cleared automatically when
        the set of enabled sources changes between calls.
        """
        # Re-evaluate when= routing fresh on every call.
        # If the enabled-source set changed, stale cached data is discarded.
        new_sig = tuple(i for i, s in enumerate(self._sources) if when_has_cross_refs(s) or evaluate_when_eager(s.when))
        if new_sig != self._enabled_sig:
            self._cached_data = None
            self._cached_at = None
            self._enabled_sig = new_sig

        if self._cached_data is not None and cache_is_fresh(cache=self._cache, cached_at=self._cached_at):
            return self._cached_data
        self.loading = True
        try:
            try:
                self._prepare_for_load()
                result = self._do_load()
            except (DatureError, DatureErrorGroup, DatureConfigError):
                raise
            except Exception as exc:  # noqa: BLE001
                exc.__traceback__ = None  # sub-exceptions in ExceptionGroup render their own tb even when outer tb=None
                raise DatureConfigError(self._schema.__name__, [exc]) from None
        finally:
            self.loading = False
        if self._cache is not False:
            self._cached_data = result
            self._cached_at = _aligned_now(self._cache)
        return result

    @staticmethod
    def as_decorator(  # noqa: PLR0913
        *sources: Source,
        cache: bool | timedelta | None = None,
        debug: bool | None = None,
        strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
        field_merges: FieldMergeMap | None = None,
        field_groups: tuple[FieldGroupTuple, ...] = (),
        skip_broken_sources: bool = False,
        skip_invalid_fields: bool = False,
        expand_env_vars: ExpandEnvVarsMode | None = None,
        secret_field_names: tuple[str, ...] | None = None,
        mask_secrets: bool | None = None,
        type_loaders: TypeLoaderMap | None = None,
        nested_resolve_strategy: NestedResolveStrategy | None = None,
        nested_resolve: NestedResolve | None = None,
    ) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]:
        """Return a decorator that wires ``cls.__init__`` through a ``Loader`` instance."""

        def decorator(target_cls: type[DataclassInstance]) -> type[DataclassInstance]:
            if not is_dataclass(target_cls):
                msg = f"{target_cls.__name__} must be a dataclass"
                raise TypeError(msg)
            loader = Loader(
                *sources,
                schema=target_cls,
                cache=cache,
                debug=debug,
                strategy=strategy,
                field_merges=field_merges,
                field_groups=field_groups,
                skip_broken_sources=skip_broken_sources,
                skip_invalid_fields=skip_invalid_fields,
                expand_env_vars=expand_env_vars,
                secret_field_names=secret_field_names,
                mask_secrets=mask_secrets,
                type_loaders=type_loaders,
                nested_resolve_strategy=nested_resolve_strategy,
                nested_resolve=nested_resolve,
            )
            target_cls.__init__ = _make_patched_init(loader)  # type: ignore[method-assign]
            target_cls.__post_init__ = make_validating_post_init(loader)  # type: ignore[attr-defined]
            return target_cls

        return decorator

    # ------------------------------------------------------------------ #
    # Internal — used by the decorator's patched ``__init__``.
    # ------------------------------------------------------------------ #

    # PatchContext protocol fields exposed publicly: ``cls``, ``loading``,
    # ``validating``, ``original_post_init``, ``validation_loader``,
    # ``error_ctx``. These are public attributes (no leading underscore) so the
    # ``make_validating_post_init`` helper can reach them directly.

    @property
    def source(self) -> Source:
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
            skip_broken_sources=self._skip_broken_sources,
            skip_invalid_fields=self._skip_invalid_fields,
            secret_field_names=self._secret_field_names,
            mask_secrets=self._mask_secrets_arg,
            type_loaders=self._type_loaders_arg,
        )

        if self._is_single:
            source = self._merge_meta.sources[0]
            # Apply $$ → $ escaping. Multi-mode does this inside LoadCtx._prepare_source
            # where each source's context is already available; for single-mode there are
            # no cross-ref deps, so we can run it with an empty context immediately.
            source = clone_with_interpolation(source, {})
            source.validate()
            self._merge_meta.sources = (source,)
            self._source = source
            self._type_loaders = resolve_type_loaders(source, self._type_loaders_arg)
            self._probe_retort = source.retorts.get(probe_retort_key(self._type_loaders))

    def _build_validation_loader(self, source: Source) -> tuple[Callable[[JSONValue], DataclassInstance], ErrorContext]:
        """Build (validation_loader_fn, error_ctx) for *source*, reusing the pre-warmed retort."""
        source_type_loaders = resolve_type_loaders(source, self._type_loaders_arg)
        # Retort pre-built in __init__ and stored per-source; stable across clone_source
        # (shallow copy shares the retorts dict). A KeyError here is a logic error.
        validating_retort = source.retorts[validating_retort_key(source_type_loaders)]
        loader_fn = validating_retort.get_loader(self._schema)
        resolved_mask_secrets = resolve_mask_secrets(load_level=self._mask_secrets_arg)
        ctx = build_error_ctx(
            source,
            self._schema.__name__,
            secret_paths=self.secret_paths,
            mask_secrets=resolved_mask_secrets,
        )
        # Keep protocol-exposed attributes in sync for make_validating_post_init consumers.
        self.validation_loader = loader_fn
        self.error_ctx = ctx
        return loader_fn, ctx

    def _do_load(self) -> T:
        if self._is_single:
            return self._do_load_single()
        return self._do_load_multi()

    def _do_load_single(self) -> T:  # noqa: C901
        source: Source = self._source  # type: ignore[assignment]  # set by _prepare_for_load
        schema = self._schema

        validation_loader, error_ctx = self._build_validation_loader(source)

        load_result = handle_load_errors(
            func=source.load_raw,
            ctx=error_ctx,
        )
        raw_data = load_result.data

        if load_result.nested_conflicts:
            error_ctx = build_error_ctx(
                source,
                schema.__name__,
                secret_paths=self.secret_paths,
                mask_secrets=error_ctx.mask_secrets,
                nested_conflicts=load_result.nested_conflicts,
            )
            self.error_ctx = error_ctx

        filter_result = apply_skip_invalid(
            raw=raw_data,
            skip_field_if_invalid=source.skip_field_if_invalid,
            source=source,
            schema=schema,
            log_prefix=f"[{schema.__name__}]",
            probe_retort=self._probe_retort,
        )
        raw_data = filter_result.cleaned_dict

        skipped_fields: dict[str, list[SkippedFieldSource]] = {}
        file_content = read_file_content(
            error_ctx.source.file_path_for_errors(),
            error_ctx.source.encoding_for_errors(),
        )
        for path in filter_result.skipped_paths:
            skipped_fields.setdefault(path, []).append(
                SkippedFieldSource(source=source, error_ctx=error_ctx, file_content=file_content),
            )

        format_name = source.format_name
        report: LoadReport | None = None
        if self.debug:
            source_path = source.file_path_for_errors()
            report_file_path = str(source_path) if source_path is not None else source.display_name()
            report = _build_single_source_report(
                dataclass_name=schema.__name__,
                loader_type=format_name,
                file_path=report_file_path,
                raw_data=raw_data,
                secret_paths=self.secret_paths,
            )

        _log_single_source_load(
            dataclass_name=schema.__name__,
            loader_type=format_name,
            file_path=source.display_name(),
            data=raw_data if isinstance(raw_data, dict) else {},
            secret_paths=self.secret_paths,
        )

        raw_data = coerce_flag_fields(raw_data, schema)

        try:
            handle_load_errors(
                func=lambda: validation_loader(raw_data),
                ctx=error_ctx,
            )
        except DatureConfigError as exc:
            if report is not None:
                attach_load_report(schema, report)
            if skipped_fields:
                raise enrich_skipped_errors(exc, skipped_fields) from exc
            raise

        try:
            result = handle_load_errors(
                func=lambda: transform_to_dataclass(
                    source,
                    raw_data,
                    schema,
                    resolved_type_loaders=self._type_loaders,
                ),
                ctx=error_ctx,
            )
        except DatureConfigError as exc:
            if report is not None:
                attach_load_report(schema, report)
            if skipped_fields:
                raise enrich_skipped_errors(exc, skipped_fields) from exc
            raise

        if report is not None:
            attach_load_report(result, report)

        return result

    def _run_merge(self) -> "_MergedData[T]":
        """Execute load_and_merge and return the raw MergeResult."""
        return load_and_merge(
            merge_meta=self._merge_meta,  # type: ignore[arg-type]  # set by _prepare_for_load
            schema=self._schema,
            debug=self.debug,
            secret_paths=self.secret_paths,
        )

    def _validate_merged(self, data: "_MergedData[T]") -> T:
        """Validate the merged result using the runtime last_source's retort."""
        validation_loader, last_error_ctx = self._build_validation_loader(data.last_source)
        try:
            handle_load_errors(
                func=lambda: validation_loader(data.merged_raw),
                ctx=last_error_ctx,
            )
        except DatureConfigError:
            if self.debug:
                report = get_load_report(data.result)
                if report is not None:
                    attach_load_report(self._schema, report)
            raise
        return data.result

    def _do_load_multi(self) -> T:
        data = self._run_merge()
        return self._validate_merged(data)


def _make_patched_init(loader: Loader[Any]) -> Callable[..., None]:
    """Build the ``__init__`` replacement that delegates loading to ``loader``."""

    def new_init(self: DataclassInstance, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        if loader.loading:
            loader.original_init(self, *args, **kwargs)
            return

        loaded_data = loader.load()
        complete_kwargs = merge_fields(loaded_data, loader.field_list, args, kwargs)
        loader.original_init(self, *args, **complete_kwargs)

        if loader.debug:
            _attach_debug_report(self, loaded_data)

        if loader.original_post_init is None:
            self.__post_init__()  # type: ignore[attr-defined]

    return new_init


def _attach_debug_report(instance: DataclassInstance, loaded_data: DataclassInstance) -> None:
    """Attach a ``LoadReport`` to ``instance`` after a decorator-driven construction."""
    report = get_load_report(loaded_data)
    if report is not None:
        attach_load_report(instance, report)
