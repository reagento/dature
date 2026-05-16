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
from dataclasses import asdict, fields, is_dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from dature.config import config
from dature.errors import DatureConfigError
from dature.errors.formatter import enrich_skipped_errors, handle_load_errors
from dature.errors.location import read_file_content
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
from dature.loading.merge import _collect_extra_secret_patterns, _load_and_merge
from dature.loading.merge_config import (
    MergeConfig,
    SourceParams,
    apply_source_config_defaults,
    apply_source_init_params,
)
from dature.loading.source_loading import SkippedFieldSource, resolve_type_loaders
from dature.masking.detection import build_secret_paths
from dature.masking.masking import mask_json_value
from dature.protocols import DataclassInstance
from dature.sources.base import Source
from dature.sources.retort import (
    create_probe_retort,
    create_validating_retort,
    ensure_retort,
    transform_to_dataclass,
)
from dature.strategies.source import SourceMergeStrategy
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

if TYPE_CHECKING:
    from adaptix import Retort

    from dature.errors.location import ErrorContext

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
    """Encapsulates a ``load`` call. ``.load()`` honours the cache; ``.invalidate()`` clears it."""

    def __init__(  # noqa: C901, PLR0913, PLR0915
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

        self._sources = sources
        self._schema = schema
        self._cache: bool | timedelta = cache
        self._debug = debug

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

        source_params = SourceParams(
            expand_env_vars=expand_env_vars,
            nested_resolve_strategy=nested_resolve_strategy,
            nested_resolve=nested_resolve,
        )

        if len(sources) > 1:
            self._merge_meta: MergeConfig | None = MergeConfig(
                sources=sources,
                source_params=source_params,
                strategy=strategy,
                field_merges=field_merges,
                field_groups=field_groups,
                skip_broken_sources=skip_broken_sources,
                skip_invalid_fields=skip_invalid_fields,
                secret_field_names=secret_field_names,
                mask_secrets=mask_secrets,
                type_loaders=type_loaders,
            )
            # Pre-prep retorts for every source in the merge.
            for src in self._merge_meta.sources:
                src_type_loaders = resolve_type_loaders(src, self._merge_meta.type_loaders)
                ensure_retort(src, schema, resolved_type_loaders=src_type_loaders)

            last_source = self._merge_meta.sources[-1]
            last_type_loaders = resolve_type_loaders(last_source, self._merge_meta.type_loaders)
            validating_retort = create_validating_retort(
                last_source,
                schema,
                resolved_type_loaders=last_type_loaders,
            )
            self.validation_loader: Callable[[JSONValue], DataclassInstance] = validating_retort.get_loader(schema)

            resolved_mask_secrets = resolve_mask_secrets(load_level=self._merge_meta.mask_secrets)
            self.secret_paths: frozenset[str] = frozenset()
            if resolved_mask_secrets:
                extra_patterns = _collect_extra_secret_patterns(self._merge_meta)
                self.secret_paths = build_secret_paths(schema, extra_patterns=extra_patterns)

            self.error_ctx: ErrorContext = build_error_ctx(
                last_source,
                schema.__name__,
                secret_paths=self.secret_paths,
                mask_secrets=resolved_mask_secrets,
            )

            self._source: Source | None = None
            self._type_loaders: TypeLoaderMap | None = None
            self._probe_retort: Retort | None = None
        else:
            self._merge_meta = None
            single_source = apply_source_config_defaults(apply_source_init_params(sources[0], source_params))
            self._source = single_source
            self._secret_field_names = secret_field_names
            self._mask_secrets_arg = mask_secrets

            self._type_loaders = resolve_type_loaders(single_source, type_loaders)
            ensure_retort(single_source, schema, resolved_type_loaders=self._type_loaders)
            validating_retort = create_validating_retort(
                single_source,
                schema,
                resolved_type_loaders=self._type_loaders,
            )
            self.validation_loader = validating_retort.get_loader(schema)

            resolved_mask_secrets = resolve_mask_secrets(load_level=mask_secrets)
            self.secret_paths = frozenset()
            if resolved_mask_secrets:
                extra_patterns = secret_field_names or ()
                self.secret_paths = build_secret_paths(schema, extra_patterns=extra_patterns)

            self.error_ctx = build_error_ctx(
                single_source,
                schema.__name__,
                secret_paths=self.secret_paths,
                mask_secrets=resolved_mask_secrets,
            )

            # probe_retort is created early so adaptix sees the original signature.
            self._probe_retort = None
            if single_source.skip_field_if_invalid:
                self._probe_retort = create_probe_retort(single_source, resolved_type_loaders=self._type_loaders)
                self._probe_retort.get_loader(schema)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def load(self) -> T:
        if self._cached_data is not None and cache_is_fresh(cache=self._cache, cached_at=self._cached_at):
            return self._cached_data
        self.loading = True
        try:
            result = self._do_load()
        finally:
            self.loading = False
        if self._cache is not False:
            self._cached_data = result
            self._cached_at = _aligned_now(self._cache)
        return result

    def invalidate(self) -> None:
        """Drop the cached result so the next ``.load()`` reloads from sources."""
        self._cached_data = None
        self._cached_at = None

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
    def probe_retort(self) -> "Retort | None":
        return self._probe_retort

    # ------------------------------------------------------------------ #
    # Loading machinery
    # ------------------------------------------------------------------ #

    def _do_load(self) -> T:
        if self._merge_meta is not None:
            return self._do_load_multi()
        return self._do_load_single()

    def _do_load_single(self) -> T:  # noqa: C901
        assert self._source is not None  # noqa: S101 — invariant for single mode
        source = self._source
        schema = self._schema

        load_result = handle_load_errors(
            func=source.load_raw,
            ctx=self.error_ctx,
        )
        raw_data = load_result.data

        if load_result.nested_conflicts:
            self.error_ctx = build_error_ctx(
                source,
                schema.__name__,
                secret_paths=self.secret_paths,
                mask_secrets=self.error_ctx.mask_secrets,
                nested_conflicts=load_result.nested_conflicts,
            )

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
        file_content = read_file_content(self.error_ctx.source.file_path_for_errors())
        for path in filter_result.skipped_paths:
            skipped_fields.setdefault(path, []).append(
                SkippedFieldSource(source=source, error_ctx=self.error_ctx, file_content=file_content),
            )

        format_name = source.format_name
        report: LoadReport | None = None
        if self._debug:
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
                func=lambda: self.validation_loader(raw_data),
                ctx=self.error_ctx,
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
                ctx=self.error_ctx,
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

    def _do_load_multi(self) -> T:
        assert self._merge_meta is not None  # noqa: S101 — invariant for multi mode
        data = _load_and_merge(
            merge_meta=self._merge_meta,
            schema=self._schema,
            debug=self._debug,
        )

        # Re-validate against the last source's retort (already pre-built in __init__).
        last_error_ctx = build_error_ctx(
            data.last_source,
            self._schema.__name__,
            secret_paths=self.secret_paths,
            mask_secrets=self.error_ctx.mask_secrets,
        )
        try:
            handle_load_errors(
                func=lambda: self.validation_loader(data.merged_raw),
                ctx=last_error_ctx,
            )
        except DatureConfigError:
            if self._debug:
                report = get_load_report(data.result)
                if report is not None:
                    attach_load_report(self._schema, report)
            raise

        # Keep the error_ctx in sync with the last loaded source for
        # subsequent re-entries (decorator mode).
        self.error_ctx = last_error_ctx
        return data.result


def _make_patched_init(loader: Loader[Any]) -> Callable[..., None]:
    """Build the ``__init__`` replacement that delegates loading to ``loader``."""

    def new_init(self: DataclassInstance, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        if loader.loading:
            loader.original_init(self, *args, **kwargs)
            return

        loaded_data = loader.load()
        complete_kwargs = merge_fields(loaded_data, loader.field_list, args, kwargs)
        loader.original_init(self, *args, **complete_kwargs)

        if loader._debug:  # noqa: SLF001
            _attach_debug_report(self, loader, loaded_data)

        if loader.original_post_init is None:
            self.__post_init__()  # type: ignore[attr-defined]

    return new_init


def _attach_debug_report(instance: DataclassInstance, loader: Loader[Any], loaded_data: DataclassInstance) -> None:
    """Attach a ``LoadReport`` to ``instance`` after a decorator-driven construction."""
    if loader._merge_meta is not None:  # noqa: SLF001
        report = get_load_report(loaded_data)
        if report is not None:
            attach_load_report(instance, report)
        return

    # Single-source: build a fresh report from the final dict so post-construction
    # mutations (validators, __post_init__) are reflected.
    result_dict = asdict(instance)
    source = loader.source
    source_path = source.file_path_for_errors()
    report = _build_single_source_report(
        dataclass_name=loader.cls.__name__,
        loader_type=source.format_name,
        file_path=str(source_path) if source_path is not None else source.display_name(),
        raw_data=result_dict,
        secret_paths=loader.secret_paths,
    )
    attach_load_report(instance, report)
