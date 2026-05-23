"""Merge-runtime triangle: ``MergeConfig`` ↔ ``SourceMergeStrategy`` ↔ ``LoadCtx``.

These three types form a mutual-annotation triangle that must live in one
module to keep every import on the module top-level without ``TYPE_CHECKING``:

- ``MergeConfig.strategy: SourceMergeStrategy``
- ``SourceMergeStrategy.__call__(ctx: LoadCtx)``
- ``LoadCtx.__init__(merge_meta: MergeConfig)``

Value types touched by ``LoadCtx`` (``SourceEntry`` / ``FieldOrigin`` from
``report_types``, ``SkippedFieldSource`` from ``errors.location``) are
imported on the module top-level — those modules no longer pull in
``merge_runtime`` (``LoadReport`` itself lives in ``dature.load_report``).
Per-source helpers (``resolve_type_loaders``, ``should_skip_broken``,
``resolve_skip_invalid``, ``apply_merge_skip_invalid``) live here rather than
in ``loading.source_loading`` so that ``source_loading`` can import
``MergeConfig`` at module level without forming a cycle.
"""

import copy
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from typing import Protocol, TypeVar, runtime_checkable

from dature.config import config
from dature.errors import DatureConfigError, SourceLoadError, SourceLocation
from dature.errors.formatter import handle_load_errors
from dature.errors.location import SkippedFieldSource, SourceContext, read_file_content
from dature.field_path import FieldPath
from dature.loading.context import apply_skip_invalid, build_error_ctx
from dature.masking.masking import mask_json_value
from dature.merging.deep_merge import deep_merge_last_wins
from dature.protocols import DataclassInstance
from dature.report_types import FieldOrigin, SourceEntry
from dature.skip_field_provider import FilterResult
from dature.sources.base import Source
from dature.types import (
    ExpandEnvVarsMode,
    FieldGroupTuple,
    FieldMergeMap,
    JSONValue,
    MergeStrategyName,
    NestedResolve,
    NestedResolveStrategy,
    SystemConfigDirsArg,
    TypeLoaderMap,
)

logger = logging.getLogger("dature")

_MISSING: object = object()

TSource = TypeVar("TSource", bound=Source)


@dataclass(frozen=True, kw_only=True)
class SourceParams:
    """Load-level defaults applied to every Source before loading."""

    expand_env_vars: ExpandEnvVarsMode | None = None
    nested_resolve_strategy: NestedResolveStrategy | None = None
    nested_resolve: NestedResolve | None = None
    search_system_paths: bool | None = None
    system_config_dirs: SystemConfigDirsArg | None = None
    encoding: str | None = None


def apply_source_init_params[T: Source](source: T, params: SourceParams) -> T:
    """Inject load-level params into source fields (source > load > config).

    Iterates SourceParams fields by name and matches them against the source's
    dataclass fields. For each matching field currently None: applies
    load-level value, or falls back to config.loading.<same_name> if available.
    """
    source_field_names = {f.name for f in fields(source) if f.init}
    overrides: dict[str, object] = {}

    for f in fields(params):
        name = f.name
        if name not in source_field_names:
            continue
        if getattr(source, name, None) is not None:
            continue  # source-level takes priority
        load_val = getattr(params, name)
        config_val = getattr(config.loading, name, None)
        effective = load_val if load_val is not None else config_val
        if effective is not None:
            overrides[name] = effective

    if not overrides:
        return source

    new_source = copy.copy(source)
    new_dict = vars(new_source)
    new_dict.update(overrides)
    # `FileFieldMixin._resolved_file_path` is a cached_property whose value lives in
    # `__dict__`; drop it so it re-resolves against the overridden inputs
    # (search_system_paths, system_config_dirs) instead of returning a stale result.
    new_dict.pop("_resolved_file_path", None)
    return new_source


def apply_source_config_defaults[T: Source](source: T) -> T:
    """Fill None-valued source fields from ``dature.config.<source.config_group>``,
    then invoke ``source._validate()`` so post-merge invariants are checked exactly once
    on the path between source construction and ``load_raw()``.

    Sources whose connection/credential params are typically configured globally
    (e.g. ``VaultSource`` → ``config.vault``) opt in via the ClassVar
    ``config_group``. Source-level non-None values always win; this only fills gaps.
    Sources without a ``config_group`` skip the merge step but still run ``_validate()``.
    Order: instance > load-level (apply_source_init_params) > config group (this).
    """
    group_name: str | None = getattr(type(source), "config_group", None)
    cfg_group = getattr(config, group_name, None) if group_name is not None else None

    if cfg_group is not None:
        source_field_names = {f.name for f in fields(source) if f.init}
        overrides: dict[str, object] = {}
        for f in fields(cfg_group):
            name = f.name
            if name not in source_field_names:
                continue
            if getattr(source, name, None) is not None:
                continue  # source-level wins
            cfg_val = getattr(cfg_group, name)
            if cfg_val is not None:
                overrides[name] = cfg_val

        if overrides:
            source = copy.copy(source)
            vars(source).update(overrides)

    source._validate()  # noqa: SLF001
    return source


@dataclass(slots=True, kw_only=True)
class MergeConfig:
    sources: tuple[Source, ...]
    source_params: SourceParams = field(default_factory=SourceParams)
    strategy: "MergeStrategyName | SourceMergeStrategy" = "last_wins"
    field_merges: FieldMergeMap | None = None
    field_groups: tuple[FieldGroupTuple, ...] = ()
    skip_broken_sources: bool = False
    skip_invalid_fields: bool = False
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
    type_loaders: TypeLoaderMap | None = None

    def __post_init__(self) -> None:
        self.sources = tuple(
            apply_source_config_defaults(apply_source_init_params(s, self.source_params)) for s in self.sources
        )


def _flatten_dict(data: JSONValue, *, prefix: str) -> list[tuple[str, JSONValue]]:
    """Flatten nested dicts into dot-separated key-value pairs (leaf nodes only)."""
    if not isinstance(data, dict):
        return []

    result: list[tuple[str, JSONValue]] = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(_flatten_dict(value, prefix=full_key))
        else:
            result.append((full_key, value))
    return result


def resolve_type_loaders(
    source: Source,
    load_type_loaders: TypeLoaderMap | None,
) -> TypeLoaderMap | None:
    merged = {**config.type_loaders, **(load_type_loaders or {}), **(source.type_loaders or {})}
    return merged or None


def should_skip_broken(source: Source, merge_meta: MergeConfig) -> bool:
    if source.skip_if_broken is not None:
        if source.file_display() is None:
            logger.warning(
                "skip_if_broken has no effect on non-file sources — they cannot be broken",
            )
        return source.skip_if_broken
    return merge_meta.skip_broken_sources


def resolve_skip_invalid(
    source: Source,
    merge_meta: MergeConfig,
) -> bool | tuple[FieldPath, ...]:
    if source.skip_field_if_invalid is not None:
        return source.skip_field_if_invalid
    return merge_meta.skip_invalid_fields


def apply_merge_skip_invalid(
    *,
    raw: JSONValue,
    source: Source,
    merge_meta: MergeConfig,
    schema: type[DataclassInstance],
    source_index: int,
) -> FilterResult:
    skip_value = resolve_skip_invalid(source, merge_meta)
    if not skip_value:
        return FilterResult(cleaned_dict=raw, skipped_paths=[])

    return apply_skip_invalid(
        raw=raw,
        skip_field_if_invalid=skip_value,
        source=source,
        schema=schema,
        log_prefix=f"[{schema.__name__}] Source {source_index}:",
    )


@dataclass(frozen=True, slots=True)
class _LoadReport:
    """Snapshot of metadata accumulated by ``LoadCtx`` during strategy execution.

    Internal type — used by ``multi.py`` caller to drive transform_to_dataclass,
    get_load_report, and error enrichment. Not exposed to merge strategies.
    """

    raw_dicts: list[JSONValue]
    source_entries: list[SourceEntry]
    source_ctxs: list[SourceContext]
    skipped_fields: dict[str, list[SkippedFieldSource]]
    last_source: Source | None
    last_type_loaders: TypeLoaderMap | None


@dataclass(frozen=True, slots=True, kw_only=True)
class MergeStepEvent:
    """Emitted after each per-source merge step inside a ``SourceMergeStrategy``.

    Built-in strategies emit one event per consumed source via
    :meth:`LoadCtx.record_merge_step`. Custom strategies can emit them too if
    they want their merge progress to appear in the dature debug log.
    """

    step_idx: int
    source: Source
    source_data: JSONValue
    before: JSONValue
    after: JSONValue


class LoadCtx:
    """Helper passed to :class:`SourceMergeStrategy` ``__call__``.

    Encapsulates per-source pre-processing (param injection, type loaders,
    error-context construction, broken-source handling, ``nested_conflicts``
    rebuild, ``skip_field_if_invalid`` filtering, masking).

    Strategies call :meth:`load` for each source they want to consume; results
    are cached so repeated calls do not re-parse the source. Internal
    accumulators are exposed only via private API for built-in strategies and
    the caller in ``multi.py``.
    """

    def __init__(  # noqa:PLR0913
        self,
        *,
        merge_meta: MergeConfig,
        schema: type[DataclassInstance],
        dataclass_name: str,
        field_merge_paths: frozenset[str] | None = None,
        secret_paths: frozenset[str] = frozenset(),
        mask_secrets: bool = False,
        on_merge_step: Callable[[MergeStepEvent], None] | None = None,
    ) -> None:
        self.dataclass_name = dataclass_name
        self.field_merge_paths = field_merge_paths

        self._merge_meta = merge_meta
        self._schema = schema
        self._secret_paths = secret_paths
        self._mask_secrets = mask_secrets
        self._on_merge_step = on_merge_step

        self._raw_dicts: list[JSONValue] = []
        self._source_entries: list[SourceEntry] = []
        self._source_ctxs: list[SourceContext] = []
        self._skipped_fields: dict[str, list[SkippedFieldSource]] = {}
        self._last_source: Source | None = None
        self._last_type_loaders: TypeLoaderMap | None = None
        self._cache: dict[int, JSONValue | None] = {}
        self._next_index = 0
        self._merge_step_idx = 0
        self._source_idx_by_id: dict[int, int] = {}
        self._field_origins: dict[str, FieldOrigin] = {}

    def merge(
        self,
        *,
        source: Source,
        base: JSONValue,
        op: Callable[[JSONValue, JSONValue], JSONValue] = deep_merge_last_wins,
        skip_on_error: bool = False,
    ) -> JSONValue:
        """Apply ``source`` to ``base`` using ``op``, recording the step.

        Loads ``source`` (cached), runs ``op(base, source_data)``, registers a
        merge step (drives debug logs and ``field_origins``). Returns the new
        base. If the source is broken and skipped, returns ``base`` unchanged.

        This is the primary API for custom merge strategies — calling it after
        each per-source step is the only thing a custom strategy needs to do
        for full integration with dature's logging and ``LoadReport``.
        """
        source_data = self.load(source, skip_on_error=skip_on_error)
        if source_data is None:
            return base
        after = op(base, source_data)
        self._record_merge_step(source=source, source_data=source_data, before=base, after=after)
        return after

    def field_origins(self) -> tuple[FieldOrigin, ...]:
        """Snapshot of accumulated field origins after the strategy has finished.

        Computed from the per-step deltas recorded inside :meth:`merge` —
        works correctly for any strategy that funnels its merges through
        ``ctx.merge``.
        """
        return tuple(self._field_origins[k] for k in sorted(self._field_origins))

    def _record_merge_step(
        self,
        *,
        source: Source,
        source_data: JSONValue,
        before: JSONValue,
        after: JSONValue,
    ) -> None:
        if self._on_merge_step is not None:
            self._on_merge_step(
                MergeStepEvent(
                    step_idx=self._merge_step_idx,
                    source=source,
                    source_data=source_data,
                    before=before,
                    after=after,
                ),
            )
            self._merge_step_idx += 1

        idx = self._source_idx_by_id.get(id(source))
        if idx is None or not isinstance(after, dict):
            return
        entry = self._source_entries[idx]
        before_flat = dict(_flatten_dict(before, prefix="")) if isinstance(before, dict) else {}
        for key, val in _flatten_dict(after, prefix=""):
            if before_flat.get(key, _MISSING) != val:
                self._field_origins[key] = FieldOrigin(
                    key=key,
                    value=val,
                    source_index=idx,
                    source_file=entry.file_path,
                    source_loader_type=entry.loader_type,
                )

    def load(self, source: Source, *, skip_on_error: bool = False) -> JSONValue | None:
        """Load one source with full pre-processing.

        Returns ``None`` when the source is broken and ``skip_if_broken`` is
        active for it (or when ``skip_on_error=True``); raises
        :class:`DatureConfigError` otherwise.

        ``skip_on_error=True`` tells the load to swallow the error and return
        ``None`` regardless of the user's ``skip_if_broken`` /
        ``skip_broken_sources`` settings — useful for strategies that treat
        broken sources as a normal case (e.g. :class:`SourceFirstFound`,
        which tries sources in order and is meant to tolerate misses).

        Repeated calls with the same source object return the cached result
        without re-parsing.
        """
        cache_key = id(source)
        if cache_key in self._cache:
            return self._cache[cache_key]

        i = self._next_index
        self._next_index += 1

        type_loaders = resolve_type_loaders(source, self._merge_meta.type_loaders)
        error_ctx = build_error_ctx(
            source,
            self.dataclass_name,
            secret_paths=self._secret_paths,
            mask_secrets=self._mask_secrets,
        )

        try:
            load_result = handle_load_errors(func=source.load_raw, ctx=error_ctx)
        except (DatureConfigError, FileNotFoundError):
            if not (skip_on_error or should_skip_broken(source, self._merge_meta)):
                raise
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                self.dataclass_name,
                i,
                source.display_name(),
            )
            self._cache[cache_key] = None
            return None
        except Exception as exc:
            if not (skip_on_error or should_skip_broken(source, self._merge_meta)):
                location = SourceLocation(
                    location_label=source.location_label,
                    file_path=error_ctx.source.file_path_for_errors(),
                    line_range=None,
                    line_content=None,
                    env_var_name=None,
                )
                source_error = SourceLoadError(
                    message=str(exc),
                    location=location,
                )
                raise DatureConfigError(self.dataclass_name, [source_error]) from exc
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                self.dataclass_name,
                i,
                source.display_name(),
            )
            self._cache[cache_key] = None
            return None

        raw = load_result.data
        if load_result.nested_conflicts:
            error_ctx = build_error_ctx(
                source,
                self.dataclass_name,
                secret_paths=self._secret_paths,
                mask_secrets=self._mask_secrets,
                nested_conflicts=load_result.nested_conflicts,
            )

        file_content = read_file_content(error_ctx.source.file_path_for_errors())

        filter_result = apply_merge_skip_invalid(
            raw=raw,
            source=source,
            merge_meta=self._merge_meta,
            schema=self._schema,
            source_index=i,
        )

        for path in filter_result.skipped_paths:
            self._skipped_fields.setdefault(path, []).append(
                SkippedFieldSource(source=source, error_ctx=error_ctx, file_content=file_content),
            )

        raw = filter_result.cleaned_dict

        format_name = type(source).format_name

        logger.debug(
            "[%s] Source %d loaded: loader=%s, file=%s, keys=%s",
            self.dataclass_name,
            i,
            format_name,
            source.display_name(),
            sorted(raw.keys()) if isinstance(raw, dict) else "<non-dict>",
        )
        if self._secret_paths:
            masked_raw = mask_json_value(raw, secret_paths=self._secret_paths)
        else:
            masked_raw = raw
        logger.debug(
            "[%s] Source %d raw data: %s",
            self.dataclass_name,
            i,
            masked_raw,
        )

        self._source_idx_by_id[id(source)] = len(self._source_entries)
        self._source_entries.append(
            SourceEntry(
                index=i,
                file_path=str(src_path)
                if (src_path := source.file_path_for_errors()) is not None
                else source.display_name(),
                loader_type=format_name,
                raw_data=raw,
            ),
        )
        self._source_ctxs.append(SourceContext(error_ctx=error_ctx, file_content=file_content))
        self._raw_dicts.append(raw)
        self._last_source = source
        self._last_type_loaders = type_loaders

        self._cache[cache_key] = raw
        return raw

    def loaded_raw_dicts(self) -> list[JSONValue]:
        """Snapshot of all successfully-loaded raw dicts in load order.

        Internal API for the caller in ``multi.py`` and built-in strategies
        that need access to raw data post-load (e.g. ``SourceRaiseOnConflict``
        for conflict detection). Custom strategies should not need this.
        """
        return list(self._raw_dicts)

    def loaded_source_ctxs(self) -> list[SourceContext]:
        """Snapshot of source-contexts for successfully-loaded sources.

        Internal API for the caller in ``multi.py`` and built-in strategies
        that need it (conflict detection, error reporting). Custom strategies
        should not need this.
        """
        return list(self._source_ctxs)

    def build_report(self) -> _LoadReport:
        """Snapshot of accumulated metadata after strategy execution.

        Internal API consumed by ``multi.py`` to drive transform_to_dataclass,
        get_load_report, and error enrichment. Custom strategies should not
        need this.
        """
        return _LoadReport(
            raw_dicts=list(self._raw_dicts),
            source_entries=list(self._source_entries),
            source_ctxs=list(self._source_ctxs),
            skipped_fields=dict(self._skipped_fields),
            last_source=self._last_source,
            last_type_loaders=self._last_type_loaders,
        )


@runtime_checkable
class SourceMergeStrategy(Protocol):
    def __call__(self, sources: Sequence[Source], ctx: LoadCtx) -> JSONValue: ...
