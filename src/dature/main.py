import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any, overload

from dature.config import config
from dature.loading.loader import Loader
from dature.loading.merge_runtime import SourceMergeStrategy
from dature.protocols import DataclassInstance
from dature.sources.base import Source
from dature.type_aliases import (
    ExpandEnvVarsMode,
    FieldGroupTuple,
    FieldMergeMap,
    MergeStrategyName,
    NestedResolve,
    NestedResolveStrategy,
    TypeLoaderMap,
)

logger = logging.getLogger("dature")

_DEFAULT_STRATEGY: Any = object()


@overload
def load[T](
    *sources: Source,
    schema: type[T],
    cache: bool | timedelta | None = None,
    debug: bool | None = None,
    strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
    field_merges: FieldMergeMap | None = None,
    field_groups: tuple[FieldGroupTuple, ...] = (),
    skip_if_broken: bool = False,
    skip_if_missing: bool = False,
    skip_invalid_fields: bool = False,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    secret_field_names: tuple[str, ...] | None = None,
    mask_secrets: bool | None = None,
    type_loaders: TypeLoaderMap | None = None,
    nested_resolve_strategy: NestedResolveStrategy | None = None,
    nested_resolve: NestedResolve | None = None,
) -> T: ...


@overload
def load(
    *sources: Source,
    schema: None = None,
    cache: bool | timedelta | None = None,
    debug: bool | None = None,
    strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
    field_merges: FieldMergeMap | None = None,
    field_groups: tuple[FieldGroupTuple, ...] = (),
    skip_if_broken: bool = False,
    skip_if_missing: bool = False,
    skip_invalid_fields: bool = False,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    secret_field_names: tuple[str, ...] | None = None,
    mask_secrets: bool | None = None,
    type_loaders: TypeLoaderMap | None = None,
    nested_resolve_strategy: NestedResolveStrategy | None = None,
    nested_resolve: NestedResolve | None = None,
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]: ...


# --8<-- [start:load]
def load(  # noqa: PLR0913
    *sources: Source,
    schema: type[Any] | None = None,
    cache: bool | timedelta | None = None,
    debug: bool | None = None,
    strategy: MergeStrategyName | SourceMergeStrategy = _DEFAULT_STRATEGY,
    field_merges: FieldMergeMap | None = None,
    field_groups: tuple[FieldGroupTuple, ...] = (),
    skip_if_broken: bool = False,
    skip_if_missing: bool = False,
    skip_invalid_fields: bool = False,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    secret_field_names: tuple[str, ...] | None = None,
    mask_secrets: bool | None = None,
    type_loaders: TypeLoaderMap | None = None,
    nested_resolve_strategy: NestedResolveStrategy | None = None,
    nested_resolve: NestedResolve | None = None,
) -> Any:
    # --8<-- [end:load]
    if cache is None:
        cache = config.loading.cache
    if isinstance(cache, timedelta) and cache < timedelta(0):
        msg = f"cache timedelta must be non-negative, got {cache!r}"
        raise ValueError(msg)
    if debug is None:
        debug = config.loading.debug

    user_set_strategy = strategy is not _DEFAULT_STRATEGY
    if not user_set_strategy:
        strategy = "last_wins"

    _validate_sources(sources)

    if len(sources) == 1 and (
        user_set_strategy
        or field_merges is not None
        or field_groups != ()
        or skip_if_broken
        or skip_if_missing
        or skip_invalid_fields
    ):
        logger.warning("Merge-related parameters have no effect with a single source")

    common_kwargs: dict[str, Any] = {
        "cache": cache,
        "debug": debug,
        "strategy": strategy,
        "field_merges": field_merges,
        "field_groups": field_groups,
        "skip_if_broken": skip_if_broken,
        "skip_if_missing": skip_if_missing,
        "skip_invalid_fields": skip_invalid_fields,
        "expand_env_vars": expand_env_vars,
        "secret_field_names": secret_field_names,
        "mask_secrets": mask_secrets,
        "type_loaders": type_loaders,
        "nested_resolve_strategy": nested_resolve_strategy,
        "nested_resolve": nested_resolve,
    }

    if schema is not None:
        # Function mode — throwaway Loader. No cache carries across calls.
        # To cache, construct ``Loader(...)`` explicitly and reuse it.
        return Loader(*sources, schema=schema, **common_kwargs).load()

    # Decorator mode — the Loader persists for the class lifetime.
    # Cache freshness is keyed on the enabled-source set (which sources are
    # active), not on source content. If an env var changes value between
    # .load() calls but the same sources remain enabled, cached data is
    # returned until the TTL (cache=timedelta(...)) expires or cache=False.
    return Loader.as_decorator(*sources, **common_kwargs)


def _validate_sources(sources: tuple[Source, ...]) -> None:
    for source in sources:
        if not isinstance(source, Source):
            msg = f"load() positional arguments must be Source instances, got {source!r}"
            raise TypeError(msg)

    if not sources:
        msg = "load() requires at least one Source"
        raise TypeError(msg)
