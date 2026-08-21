"""Merge-runtime triangle: ``MergeConfig`` ↔ ``SourceMergeStrategy`` ↔ ``LoadCtx``.

Owns the internal accumulator machinery: ``LoadCtx`` collects per-source
raw dicts, source entries, and error contexts during strategy execution, then
exposes them via ``_LoadCtxSnapshot`` (an internal bridge to ``merge.py``,
not a report type). Does *not* own the public ``LoadReport`` aggregate (that
lives in ``dature.report``) nor the frozen leaf types (``SourceEntry`` /
``FieldOrigin`` live in ``dature.report_types``).

These three types form a mutual-annotation triangle that must live in one
module to keep every import on the module top-level without ``TYPE_CHECKING``:

- ``MergeConfig.strategy: SourceMergeStrategy``
- ``SourceMergeStrategy.__call__(ctx: LoadCtx)``
- ``LoadCtx.__init__(merge_meta: MergeConfig)``

Value types touched by ``LoadCtx`` (``SourceEntry`` / ``FieldOrigin`` from
``report_types``, ``SkippedFieldSource`` from ``errors.location``) are
imported on the module top-level — those modules no longer pull in
``merge_runtime`` (``LoadReport`` itself lives in ``dature.report``).
Per-source helpers that need ``MergeConfig`` (``resolve_type_loaders``,
``should_skip_broken``, ``should_skip_missing``, ``resolve_skip_invalid``) live here rather than in
``loading.source_loading`` so that ``source_loading`` can import ``MergeConfig``
at module level without forming a cycle. The shared deterministic load-tail
(nested_conflicts rebuild, file_content read, skip_field_if_invalid filter)
lives in ``source_loading.prepare_loaded_source``.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from typing import Protocol, runtime_checkable

from dature.config import BOOTSTRAP_CONFIG, DatureConfig, LoadingConfig, resolve_config
from dature.errors import DatureConfigError, DatureError, SourceLoadError, SourceLocation
from dature.errors.extraction import handle_load_errors
from dature.errors.location import SkippedFieldSource, SourceContext
from dature.loading.context import build_error_ctx
from dature.loading.cross_source import (
    CrossRefPlan,
    build_cross_ref_plan,
    clone_with_interpolation,
    evaluate_when_lazy,
    when_has_cross_refs,
)
from dature.loading.retort import RetortCache
from dature.loading.source_loading import prepare_loaded_source
from dature.loading.source_validation import validate_source
from dature.masking.masking import mask_json_value
from dature.merging.deep_merge import deep_merge_last_wins
from dature.nested_dict import flatten_dict
from dature.protocols import DataclassInstance
from dature.report_types import FieldOrigin, SourceEntry
from dature.sources.base import IndexedSource, clone_source
from dature.sources.protocol import FileSourceProtocol, SourceProtocol
from dature.type_aliases import (
    ExpandEnvVarsMode,
    FieldGroupTuple,
    FieldMergeMap,
    JSONValue,
    MergeStrategyName,
    NestedResolve,
    NestedResolveStrategy,
    SkipFieldsInvalid,
    SystemConfigDirsArg,
    TypeLoaderMap,
)

logger = logging.getLogger("dature")

_MISSING: object = object()


@dataclass(frozen=True, kw_only=True)
class SourceParams:
    """Load-level defaults applied to every Source before loading."""

    expand_env_vars: ExpandEnvVarsMode | None = None
    nested_resolve_strategy: NestedResolveStrategy | None = None
    nested_resolve: NestedResolve | None = None
    search_system_paths: bool | None = None
    system_config_dirs: SystemConfigDirsArg | None = None
    encoding: str | None = None


def apply_source_init_params[T: SourceProtocol](
    source: T,
    params: SourceParams,
    loading: LoadingConfig | None = None,
) -> T:
    """Inject load-level params into source fields (source > load > config).

    Iterates SourceParams fields by name and matches them against the source's
    dataclass fields. For each matching field currently None: applies
    load-level value, or falls back to *loading*.<same_name> if available.
    *loading* defaults to the process-wide config.loading when omitted.
    """
    effective_loading = loading if loading is not None else resolve_config().loading
    source_field_names = {f.name for f in fields(source) if f.init}
    overrides: dict[str, object] = {}

    for f in fields(params):
        name = f.name
        if name not in source_field_names:
            continue
        if getattr(source, name, None) is not None:
            continue  # source-level takes priority
        load_val = getattr(params, name)
        config_val = getattr(effective_loading, name, None)
        effective = load_val if load_val is not None else config_val
        if effective is not None:
            overrides[name] = effective

    if not overrides:
        return source

    return clone_source(source, overrides)


def _is_unset(value: object) -> bool:
    """Whether a source field should be treated as not configured.

    ``None`` is the usual sentinel. ``""`` covers non-optional ``str`` fields
    (e.g. ``VaultSource.mount_point``) that cannot express "unset" via ``None``.
    """
    return value is None or value == ""


def apply_source_config_group[T: SourceProtocol](source: T, cfg: DatureConfig | None = None) -> T:
    """Fill unset source fields from ``<cfg>.<source.config_group>``.

    Sources whose connection/credential params are typically configured globally
    (e.g. ``VaultSource`` → ``config.vault``) opt in via the ``config_group``
    attribute. Source-level values always win; this only fills gaps — a field
    is considered a gap when it is ``None`` or ``""`` (see ``_is_unset``).
    Sources without a ``config_group`` are returned as-is.
    Order: instance > load-level (apply_source_init_params) > config group (this).

    *cfg* defaults to the process-wide config when omitted.

    Note: ``validate_source()`` is NOT called here — it runs lazily inside
    ``LoadCtx.load`` after cross-ref interpolation has been applied so that
    string fields contain real values before invariants are checked.
    """
    effective_cfg = cfg if cfg is not None else resolve_config()
    group_name: str | None = source.config_group
    cfg_group = getattr(effective_cfg, group_name, None) if group_name is not None else None

    if cfg_group is None:
        return source

    source_field_names = {f.name for f in fields(source) if f.init}
    overrides: dict[str, object] = {}
    for f in fields(cfg_group):
        name = f.name
        if name not in source_field_names:
            continue
        if not _is_unset(getattr(source, name, None)):
            continue  # source-level wins
        cfg_val = getattr(cfg_group, name)
        if not _is_unset(cfg_val):
            overrides[name] = cfg_val

    if overrides:
        source = clone_source(source, overrides)

    return source


def prepare_sources(
    sources: tuple[SourceProtocol, ...],
    params: SourceParams,
    cfg: DatureConfig | None = None,
) -> tuple[SourceProtocol, ...]:
    """Run the two-step eager source preparation pipeline.

    apply_source_init_params → apply_source_config_group
    """
    loading = cfg.loading if cfg is not None else None
    after_params = tuple(apply_source_init_params(s, params, loading) for s in sources)
    return tuple(apply_source_config_group(s, cfg) for s in after_params)


@dataclass(slots=True, kw_only=True)
class MergeConfig:
    sources: tuple[SourceProtocol, ...]
    source_params: SourceParams = field(default_factory=SourceParams)
    strategy: "MergeStrategyName | SourceMergeStrategy" = "last_wins"
    field_merges: FieldMergeMap | None = None
    field_groups: Sequence[FieldGroupTuple] = ()
    skip_if_broken: bool = False
    skip_if_missing: bool = False
    skip_field_if_invalid: SkipFieldsInvalid = None
    secret_field_names: Sequence[str] | None = None
    type_loaders: TypeLoaderMap | None = None
    config: DatureConfig = field(default=BOOTSTRAP_CONFIG)
    """Effective ``DatureConfig`` for this merge, including the effective ``masking.masking_mode``
    after any per-call override. Passed explicitly by ``Loader._prepare_for_load``; defaults to
    ``BOOTSTRAP_CONFIG`` (pure defaults, no env) so that ``MergeConfig`` constructed outside
    ``Loader`` (e.g. directly in tests) behaves deterministically."""
    cross_ref_plan: CrossRefPlan | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.sources = prepare_sources(self.sources, self.source_params, self.config)
        self.cross_ref_plan = build_cross_ref_plan(self.sources)


def resolve_type_loaders(
    source: SourceProtocol,
    load_type_loaders: TypeLoaderMap | None,
) -> TypeLoaderMap | None:
    """Merge load-level and source-level type loaders.

    Instance-level type loaders (from ``configure()`` / ``Dature``) are pre-merged into
    *load_type_loaders* at the ``Loader.__init__`` boundary, so they do not need to be
    read from the global here.  Priority: instance < load-level < source.
    """
    merged = {**(load_type_loaders or {}), **(source.type_loaders or {})}
    return merged or None


def should_skip_broken(source: SourceProtocol, merge_meta: MergeConfig) -> bool:
    """Return True if a parse/load failure for *source* should be silently skipped.

    ``when=`` filtering happens *before* this check — a source disabled by
    ``when=`` never reaches ``load_raw()`` and therefore never has a chance to
    fail.  ``skip_if_broken`` only applies to sources that pass the ``when=``
    gate and then raise a parse or config error during loading.  For missing
    files (``FileNotFoundError``) use :func:`should_skip_missing` instead.
    """
    if isinstance(source, FileSourceProtocol) and source.skip_if_broken is not None:
        return source.skip_if_broken
    return merge_meta.skip_if_broken


def should_skip_missing(source: SourceProtocol, merge_meta: MergeConfig) -> bool:
    """Return True if a missing-file error for *source* should be silently skipped.

    ``when=`` filtering happens *before* this check — a source disabled by
    ``when=`` never reaches ``load_raw()`` and therefore never has a chance to
    be absent.  ``skip_if_missing`` only applies to sources that pass the
    ``when=`` gate and then raise ``FileNotFoundError`` during loading.  For
    parse/config errors use :func:`should_skip_broken` instead.
    """
    if isinstance(source, FileSourceProtocol) and source.skip_if_missing is not None:
        return source.skip_if_missing
    return merge_meta.skip_if_missing


def resolve_skip_invalid(
    source: SourceProtocol,
    merge_meta: MergeConfig,
) -> SkipFieldsInvalid:
    if source.skip_field_if_invalid is not None:
        return source.skip_field_if_invalid
    return merge_meta.skip_field_if_invalid


@dataclass(frozen=True, slots=True)
class _LoadCtxSnapshot:
    """Snapshot of accumulator state from ``LoadCtx`` after strategy execution.

    Internal bridge from ``LoadCtx`` to ``merge.py::load_and_merge`` — carries
    raw_dicts, source_ctxs, and type_loaders needed to finalize the load. Not
    a report type; not exposed to merge strategies.
    """

    raw_dicts: list[JSONValue]
    source_entries: list[SourceEntry]
    source_ctxs: list[SourceContext]
    skipped_fields: dict[str, list[SkippedFieldSource]]
    last_loaded: IndexedSource | None
    last_type_loaders: TypeLoaderMap | None


@dataclass(frozen=True, slots=True, kw_only=True)
class MergeStepEvent:
    """Emitted after each per-source merge step inside a ``SourceMergeStrategy``.

    Built-in strategies emit one event per consumed source via
    :meth:`LoadCtx.record_merge_step`. Custom strategies can emit them too if
    they want their merge progress to appear in the dature debug log.
    """

    step_idx: int
    source: SourceProtocol
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
    the caller in ``merge.py`` (``load_and_merge``).
    """

    def __init__(  # noqa:PLR0913
        self,
        *,
        merge_meta: MergeConfig,
        schema: type[DataclassInstance],
        dataclass_name: str,
        retort_cache: RetortCache,
        field_merge_paths: frozenset[str] | None = None,
        secret_paths: frozenset[str] = frozenset(),
        on_merge_step: Callable[[MergeStepEvent], None] | None = None,
    ) -> None:
        self.dataclass_name = dataclass_name
        self.field_merge_paths = field_merge_paths

        self._merge_meta = merge_meta
        self._schema = schema
        self._retort_cache = retort_cache
        self._secret_paths = secret_paths
        self._masking = merge_meta.config.masking  # explicit MaskingConfig from the effective DatureConfig
        self._error_display = merge_meta.config.error_display
        self._on_merge_step = on_merge_step
        self._sources: list[SourceProtocol] = list(merge_meta.sources)

        self._raw_dicts: list[JSONValue] = []
        self._source_entries: list[SourceEntry] = []
        self._source_ctxs: list[SourceContext] = []
        self._skipped_fields: dict[str, list[SkippedFieldSource]] = {}
        self._last_loaded: IndexedSource | None = None
        self._last_type_loaders: TypeLoaderMap | None = None
        self._cache: dict[int, JSONValue | None] = {}
        self._next_index = 0
        self._merge_step_idx = 0
        self._entry_pos_by_source_idx: dict[int, int] = {}
        self._field_origins: dict[str, FieldOrigin] = {}
        self._enabled_by_tag: dict[str, int] = {}  # tag → source_idx, for lazy-collision check

    def merge(
        self,
        *,
        source_idx: int,
        base: JSONValue,
        op: Callable[[JSONValue, JSONValue], JSONValue] = deep_merge_last_wins,
        skip_on_error: bool = False,
    ) -> JSONValue:
        """Apply a source to ``base`` using ``op``, recording the step.

        *source_idx* is the position of the source in ``merge_meta.sources``.

        Loads the source (cached), runs ``op(base, source_data)``, registers a
        merge step (drives debug logs and ``field_origins``). Returns the new
        base. If the source is broken and skipped, returns ``base`` unchanged.
        """
        idx = source_idx
        source_data = self.load(idx, skip_on_error=skip_on_error)
        if source_data is None:
            return base
        resolved_source = self._sources[idx]
        after = op(base, source_data)
        self._record_merge_step(
            source_idx=idx,
            source=resolved_source,
            source_data=source_data,
            before=base,
            after=after,
        )
        return after

    def _resolve_dep_refs(self, source_idx: int) -> "dict[str, dict[str, JSONValue]]":
        """Load all declared dependencies and return a context dict for cross-ref expansion.

        Disabled (when=-filtered) or skipped deps contribute an empty dict so that
        ``${@tag.key:-default}`` fallbacks on downstream sources still resolve.
        """
        plan = self._merge_meta.cross_ref_plan
        context: dict[str, dict[str, JSONValue]] = {}
        if plan is None or not plan.deps[source_idx]:
            return context
        for dep_idx in plan.deps[source_idx]:
            dep_raw = self.load(dep_idx)
            dep_source = self._sources[dep_idx]
            dep_tag = dep_source.resolved_tag
            if dep_raw is None:
                context[dep_tag] = {}
                continue
            if not isinstance(dep_raw, dict):
                msg = (
                    f"{type(dep_source).__name__}(tag='{dep_tag}') is referenced "
                    f"by ${{@{dep_tag}.*}} but its loaded data is not a dict "
                    f"(got {type(dep_raw).__name__}). Cross-source references require dict-shaped sources."
                )
                raise DatureError(msg)
            context[dep_tag] = dep_raw
        return context

    def _eval_lazy_when(
        self,
        source: "SourceProtocol",
        context: "dict[str, dict[str, JSONValue]]",
    ) -> bool:
        """Return False if source has lazy when= and the condition is not met."""
        return not when_has_cross_refs(source) or evaluate_when_lazy(source.when, context)

    def _check_lazy_tag_collision(self, source: "SourceProtocol", source_idx: int) -> None:
        """Raise DatureError if two lazy-when sources with the same tag are both enabled.

        This complements the *static* tag-collision check in ``_build_dep_graph``
        (``cross_source.py``), which runs at ``MergeConfig.__post_init__`` time and
        catches collisions that are statically visible in the enabled set.  That static
        check cannot detect the case where two sources share a tag and each has a lazy
        ``when=`` condition (resolved at load time from cross-source context) — because
        both sources may pass the static filter and only reveal the collision when both
        lazy conditions evaluate to ``True`` during the actual load.  This dynamic check
        fills that gap.
        """
        if not when_has_cross_refs(source):
            return
        tag = source.resolved_tag
        if tag in self._enabled_by_tag:
            prev_idx = self._enabled_by_tag[tag]
            prev_source = self._sources[prev_idx]
            msg = (
                f"Tag collision among enabled sources: resolved_tag={tag!r} is shared by "
                f"{type(prev_source).__name__} (index {prev_idx}) and "
                f"{type(source).__name__} (index {source_idx}), "
                "both enabled by their lazy when= conditions. "
                "Use mutually exclusive when= conditions."
            )
            raise DatureError(msg)
        self._enabled_by_tag[tag] = source_idx

    def _prepare_source_and_check_enabled(self, source_idx: int) -> bool:
        """Coordinate lazy cross-ref resolution, when= evaluation, and validate_source().

        Returns False when the source's lazy ``when=`` condition is not met —
        the caller caches None and skips loading.
        """
        context = self._resolve_dep_refs(source_idx)
        if context:
            self._sources[source_idx] = clone_with_interpolation(self._sources[source_idx], context)
        source = self._sources[source_idx]
        if not self._eval_lazy_when(source, context):
            return False
        self._check_lazy_tag_collision(source, source_idx)
        validate_source(source)
        return True

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
        source_idx: int,
        source: SourceProtocol,
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

        entry_pos = self._entry_pos_by_source_idx.get(source_idx)
        if entry_pos is None or not isinstance(after, dict):
            return
        entry = self._source_entries[entry_pos]
        before_flat = dict(flatten_dict(before, prefix="")) if isinstance(before, dict) else {}
        for key, val in flatten_dict(after, prefix=""):
            if before_flat.get(key, _MISSING) != val:
                self._field_origins[key] = FieldOrigin(
                    key=key,
                    value=val,
                    source_index=source_idx,
                    source_file=entry.file_path,
                    source_loader_type=entry.loader_type,
                )

    def load(self, source_idx: int, *, skip_on_error: bool = False) -> JSONValue | None:
        """Load a source with full pre-processing.

        *source_idx* is the position of the source in ``merge_meta.sources``.

        Returns ``None`` when the source is broken and ``skip_if_broken`` is
        active for it (or when ``skip_on_error=True``); raises
        :class:`DatureConfigError` otherwise.

        ``skip_on_error=True`` tells the load to swallow the error and return
        ``None`` regardless of the user's ``skip_if_broken`` /
        ``skip_if_missing`` settings — useful for strategies that treat
        broken or missing sources as a normal case (e.g. :class:`SourceFirstFound`,
        which tries sources in order and is meant to tolerate misses).

        Repeated calls with the same index return the cached result without
        re-parsing. Cross-ref interpolation and ``validate_source()`` are applied
        lazily on first call, before ``load_raw()`` is invoked.
        """
        if source_idx in self._cache:
            return self._cache[source_idx]

        if not self._prepare_source_and_check_enabled(source_idx):
            # Lazy when= condition not met — treat as skipped (same as broken+skipped).
            self._cache[source_idx] = None
            return None

        source = self._sources[source_idx]

        i = self._next_index
        self._next_index += 1

        type_loaders = resolve_type_loaders(source, self._merge_meta.type_loaders)
        error_ctx = build_error_ctx(
            source,
            self.dataclass_name,
            secret_paths=self._secret_paths,
            masking=self._masking,
            error_display=self._error_display,
        )

        try:
            load_result = handle_load_errors(func=source.load_raw, ctx=error_ctx)
        except FileNotFoundError:
            if not (skip_on_error or should_skip_missing(source, self._merge_meta)):
                raise
            logger.warning(
                "[%s] Source %d skipped (missing): file=%s",
                self.dataclass_name,
                i,
                source.display_name(),
            )
            self._cache[source_idx] = None
            return None
        except DatureConfigError:
            if not (skip_on_error or should_skip_broken(source, self._merge_meta)):
                raise
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                self.dataclass_name,
                i,
                source.display_name(),
            )
            self._cache[source_idx] = None
            return None
        except Exception as exc:  # noqa: BLE001
            if not (skip_on_error or should_skip_broken(source, self._merge_meta)):
                location = SourceLocation(
                    location_label=source.location_label,
                    file_path=source.file_path_for_errors() if isinstance(source, FileSourceProtocol) else None,
                    line_range=None,
                    line_content=None,
                    env_var_name=None,
                )
                source_error = SourceLoadError(
                    message=str(exc),
                    location=location,
                )
                raise DatureConfigError(self.dataclass_name, [source_error]) from None
            logger.warning(
                "[%s] Source %d skipped (broken): file=%s",
                self.dataclass_name,
                i,
                source.display_name(),
            )
            self._cache[source_idx] = None
            return None

        skip_value = resolve_skip_invalid(source, self._merge_meta)
        probe_retort = (
            self._retort_cache.field_pass(
                IndexedSource(source, source_idx), skip=True, resolved_type_loaders=type_loaders
            )
            if skip_value
            else None
        )
        prepared = prepare_loaded_source(
            load_result=load_result,
            source=source,
            schema=self._schema,
            dataclass_name=self.dataclass_name,
            base_error_ctx=error_ctx,
            skip_value=skip_value,
            secret_paths=self._secret_paths,
            log_prefix=f"[{self.dataclass_name}] Source {i}:",
            probe_retort=probe_retort,
            masking=self._masking,
            error_display=self._error_display,
        )
        raw = prepared.raw_data
        error_ctx = prepared.error_ctx
        file_content = prepared.file_content
        for path, skipped_source in prepared.skipped:
            self._skipped_fields.setdefault(path, []).append(skipped_source)

        format_name = source.format_name

        logger.debug(
            "[%s] Source %d loaded: loader=%s, file=%s, keys=%s",
            self.dataclass_name,
            i,
            format_name,
            source.display_name(),
            sorted(raw.keys()) if isinstance(raw, dict) else "<non-dict>",
        )
        masked_raw = mask_json_value(raw, secret_paths=self._secret_paths, masking=self._masking)
        logger.debug(
            "[%s] Source %d raw data: %s",
            self.dataclass_name,
            i,
            masked_raw,
        )

        src_file_path = source.file_path_for_errors() if isinstance(source, FileSourceProtocol) else None
        self._entry_pos_by_source_idx[source_idx] = len(self._source_entries)
        self._source_entries.append(
            SourceEntry(
                index=i,
                file_path=str(src_file_path) if src_file_path is not None else source.display_name(),
                loader_type=format_name,
                raw_data=raw,
            ),
        )
        self._source_ctxs.append(
            SourceContext(error_ctx=error_ctx, file_content=file_content, loaded_data=prepared.loaded_data)
        )
        self._raw_dicts.append(raw)
        self._last_loaded = IndexedSource(source, source_idx)
        self._last_type_loaders = type_loaders

        self._cache[source_idx] = raw
        return raw

    def loaded_raw_dicts(self) -> list[JSONValue]:
        """Snapshot of all successfully-loaded raw dicts in load order.

        Internal API for the caller in ``merge.py`` and built-in strategies
        that need access to raw data post-load (e.g. ``SourceRaiseOnConflict``
        for conflict detection). Custom strategies should not need this.
        """
        return list(self._raw_dicts)

    def loaded_source_ctxs(self) -> list[SourceContext]:
        """Snapshot of source-contexts for successfully-loaded sources.

        Internal API for the caller in ``merge.py`` and built-in strategies
        that need it (conflict detection, error reporting). Custom strategies
        should not need this.
        """
        return list(self._source_ctxs)

    def loaded_sources(self) -> list[tuple[IndexedSource, JSONValue, SourceContext]]:
        """Return ``(indexed_source, own_raw_dict, source_ctx)`` for each successfully-loaded source.

        ``own_raw_dict`` is the raw dict **this source contributed** (after skip-invalid filtering),
        not the cumulative merged state.  Used by ``load_and_merge`` to run per-source field-pass
        validation on the fields each source actually provided.

        Internal API — consumed by ``merge.py`` after the strategy runs.
        """
        result: list[tuple[IndexedSource, JSONValue, SourceContext]] = []
        for entry, raw, ctx in zip(self._source_entries, self._raw_dicts, self._source_ctxs, strict=False):
            source = self._sources[entry.index]
            indexed = IndexedSource(source, entry.index)
            result.append((indexed, raw, ctx))
        return result

    def build_report(self) -> _LoadCtxSnapshot:
        """Snapshot of accumulated metadata after strategy execution.

        Internal API consumed by ``merge.py`` (``load_and_merge``) to drive
        transform_to_dataclass, load_report, and error enrichment. Custom
        strategies should not need this.
        """
        return _LoadCtxSnapshot(
            raw_dicts=list(self._raw_dicts),
            source_entries=list(self._source_entries),
            source_ctxs=list(self._source_ctxs),
            skipped_fields=dict(self._skipped_fields),
            last_loaded=self._last_loaded,
            last_type_loaders=self._last_type_loaders,
        )


# --8<-- [start:source-merge-strategy]
@runtime_checkable
class SourceMergeStrategy(Protocol):
    def __call__(self, sources: Sequence[SourceProtocol], ctx: LoadCtx) -> JSONValue: ...


# --8<-- [end:source-merge-strategy]
