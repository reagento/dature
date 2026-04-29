import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from dature.errors import DatureConfigError, SourceLoadError, SourceLocation
from dature.errors.formatter import handle_load_errors
from dature.errors.location import read_file_content
from dature.load_report import FieldOrigin, SourceEntry
from dature.loading.context import build_error_ctx
from dature.loading.source_loading import (
    SkippedFieldSource,
    SourceContext,
    apply_merge_skip_invalid,
    resolve_type_loaders,
    should_skip_broken,
)
from dature.masking.masking import mask_json_value
from dature.merging.deep_merge import deep_merge_first_wins, deep_merge_last_wins, raise_on_conflict
from dature.sources.base import Source
from dature.types import JSONValue, MergeStrategyName, TypeLoaderMap

_MISSING: object = object()


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


if TYPE_CHECKING:
    from dature.loading.merge_config import MergeConfig
    from dature.protocols import DataclassInstance

logger = logging.getLogger("dature")


@dataclass(frozen=True, slots=True)
class _LoadReport:
    """Snapshot of metadata accumulated by ``LoadCtx`` during strategy execution.

    Internal type — used by ``multi.py`` caller to drive transform_to_dataclass,
    get_load_report, and error enrichment. Not exposed to merge strategies.
    """

    raw_dicts: list[JSONValue]
    source_entries: list[SourceEntry]
    source_ctxs: "list[SourceContext]"
    skipped_fields: "dict[str, list[SkippedFieldSource]]"
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
        merge_meta: "MergeConfig",
        schema: "type[DataclassInstance]",
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

    def loaded_source_ctxs(self) -> "list[SourceContext]":
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


class SourceLastWins:
    def __call__(self, sources: Sequence[Source], ctx: LoadCtx) -> JSONValue:
        base: JSONValue = {}
        for src in sources:
            base = ctx.merge(source=src, base=base)
        return base


class SourceFirstWins:
    def __call__(self, sources: Sequence[Source], ctx: LoadCtx) -> JSONValue:
        base: JSONValue = {}
        for src in sources:
            base = ctx.merge(source=src, base=base, op=deep_merge_first_wins)
        return base


class SourceFirstFound:
    """Returns data from the first source that loads successfully.

    Short-circuits — sources after the first successful one are not loaded.
    Broken sources are silently skipped (legacy FIRST_FOUND semantics) via
    :py:`ctx.merge(..., skip_on_error=True)`, regardless of per-source
    ``skip_if_broken``.
    """

    def __call__(self, sources: Sequence[Source], ctx: LoadCtx) -> JSONValue:
        for src in sources:
            data = ctx.load(src, skip_on_error=True)
            if data is not None:
                return ctx.merge(source=src, base={}, skip_on_error=True)
        return {}


class SourceRaiseOnConflict:
    """Identical to :class:`SourceLastWins` in merge behaviour, with an
    additional post-merge conflict pass.

    Raises :class:`MergeConflictError` when any field has differing values
    across sources, except for fields covered by ``field_merges``. Custom
    strategies can replicate this behaviour by calling
    :func:`dature.merging.deep_merge.raise_on_conflict` against
    ``ctx.loaded_raw_dicts()`` and ``ctx.loaded_source_ctxs()``.
    """

    def __call__(self, sources: Sequence[Source], ctx: LoadCtx) -> JSONValue:
        base: JSONValue = {}
        for src in sources:
            base = ctx.merge(source=src, base=base)
        raise_on_conflict(
            ctx.loaded_raw_dicts(),
            ctx.loaded_source_ctxs(),
            ctx.dataclass_name,
            field_merge_paths=ctx.field_merge_paths,
        )
        return base


_SOURCE_BY_NAME: dict[MergeStrategyName, type[SourceMergeStrategy]] = {
    "last_wins": SourceLastWins,
    "first_wins": SourceFirstWins,
    "first_found": SourceFirstFound,
    "raise_on_conflict": SourceRaiseOnConflict,
}


def resolve_source_strategy(
    s: "MergeStrategyName | SourceMergeStrategy",
    *,
    dataclass_name: str = "<unknown>",
) -> SourceMergeStrategy:
    if isinstance(s, str):
        if s not in _SOURCE_BY_NAME:
            available = ", ".join(_SOURCE_BY_NAME)
            msg = f"invalid merge strategy: {s!r}. Available: {available}"
            raise DatureConfigError(dataclass_name, [SourceLoadError(message=msg)])
        cls: type[SourceMergeStrategy] = _SOURCE_BY_NAME[s]
        return cls()
    return s
