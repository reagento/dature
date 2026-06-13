"""Concrete source-level merge strategies plus the name → class resolver."""

from collections.abc import Sequence

from dature.errors import DatureConfigError, SourceLoadError
from dature.loading.merge_runtime import LoadCtx, SourceMergeStrategy
from dature.merging.deep_merge import deep_merge_first_wins, raise_on_conflict
from dature.sources.base import Source
from dature.type_aliases import JSONValue, MergeStrategyName


# --8<-- [start:source-last-wins-strategy]
class SourceLastWins:
    def __call__(self, sources: Sequence[Source], ctx: LoadCtx) -> JSONValue:
        base: JSONValue = {}
        for idx in range(len(sources)):
            base = ctx.merge(source_idx=idx, base=base)
        return base


# --8<-- [end:source-last-wins-strategy]


class SourceFirstWins:
    def __call__(self, sources: Sequence[Source], ctx: LoadCtx) -> JSONValue:
        base: JSONValue = {}
        for idx in range(len(sources)):
            base = ctx.merge(source_idx=idx, base=base, op=deep_merge_first_wins)
        return base


class SourceFirstFound:
    """Returns data from the first source that loads successfully.

    Short-circuits — sources after the first successful one are not loaded.
    Broken sources are silently skipped (legacy FIRST_FOUND semantics) via
    :py:`ctx.merge(..., skip_on_error=True)`, regardless of per-source
    ``skip_if_broken``.
    """

    def __call__(self, sources: Sequence[Source], ctx: LoadCtx) -> JSONValue:
        for idx in range(len(sources)):
            data = ctx.load(idx, skip_on_error=True)
            if data is not None:
                return ctx.merge(source_idx=idx, base={}, skip_on_error=True)
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
        for idx in range(len(sources)):
            base = ctx.merge(source_idx=idx, base=base)
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
    s: MergeStrategyName | SourceMergeStrategy,
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
