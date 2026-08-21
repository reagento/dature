import logging
from collections.abc import Callable, Iterable, Sequence
from datetime import timedelta
from typing import Any, overload

from dature.config import DatureConfig
from dature.loading.loader import Loader
from dature.loading.merge_runtime import SourceMergeStrategy
from dature.protocols import DataclassInstance
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import (
    ExpandEnvVarsMode,
    FieldGroupTuple,
    FieldMergeMap,
    MaskingMode,
    MergeStrategyName,
    NestedResolve,
    NestedResolveStrategy,
    SkipFieldsInvalid,
    StaleOnErrorMode,
    TypeLoaderMap,
)
from dature.validators.root import RootPredicate

logger = logging.getLogger("dature")

DEFAULT_STRATEGY: Any = object()


@overload
def load[T](
    *sources: SourceProtocol,
    schema: type[T],
    cache: bool | timedelta | None = None,
    cache_engine: bool | None = None,
    stale_on_error: StaleOnErrorMode | None = None,
    debug: bool | None = None,
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
) -> T: ...


@overload
def load(
    *sources: SourceProtocol,
    schema: None = None,
    cache: bool | timedelta | None = None,
    cache_engine: bool | None = None,
    stale_on_error: StaleOnErrorMode | None = None,
    debug: bool | None = None,
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
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]: ...


# --8<-- [start:load]
def load(  # noqa: PLR0913
    *sources: SourceProtocol,
    schema: type[Any] | None = None,
    cache: bool | timedelta | None = None,
    cache_engine: bool | None = None,
    stale_on_error: StaleOnErrorMode | None = None,
    debug: bool | None = None,
    strategy: MergeStrategyName | SourceMergeStrategy = DEFAULT_STRATEGY,
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
) -> Any:
    # --8<-- [end:load]
    return dispatch(
        *sources,
        schema=schema,
        cache=cache,
        cache_engine=cache_engine,
        stale_on_error=stale_on_error,
        debug=debug,
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
    )


def dispatch(  # noqa: PLR0913
    *sources: SourceProtocol,
    schema: type[Any] | None = None,
    cache: bool | timedelta | None = None,
    cache_engine: bool | None = None,
    stale_on_error: StaleOnErrorMode | None = None,
    debug: bool | None = None,
    strategy: MergeStrategyName | SourceMergeStrategy = DEFAULT_STRATEGY,
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
    config: DatureConfig | None = None,
) -> Any:  # noqa: ANN401
    """Internal seam behind ``load()``: identical semantics plus an explicit config override.

    ``config`` is not part of the public API — it exists so ``Dature.load()`` can thread its
    instance config through without exposing that plumbing on ``dature.load()``'s signature.
    """
    if isinstance(cache, timedelta) and cache < timedelta(0):
        msg = f"cache timedelta must be non-negative, got {cache!r}"
        raise ValueError(msg)

    user_set_strategy = strategy is not DEFAULT_STRATEGY
    if not user_set_strategy:
        strategy = "last_wins"

    _validate_sources(sources)

    if len(sources) == 1 and (
        user_set_strategy
        or field_merges is not None
        or len(field_groups) != 0
        or skip_if_broken
        or skip_if_missing
        or skip_field_if_invalid
    ):
        logger.warning("Merge-related parameters have no effect with a single source")

    common_kwargs: dict[str, Any] = {
        "cache": cache,
        "cache_engine": cache_engine,
        "stale_on_error": stale_on_error,
        "debug": debug,
        "strategy": strategy,
        "field_merges": field_merges,
        "field_groups": field_groups,
        "root_validators": root_validators,
        "skip_if_broken": skip_if_broken,
        "skip_if_missing": skip_if_missing,
        "skip_field_if_invalid": skip_field_if_invalid,
        "expand_env_vars": expand_env_vars,
        "secret_field_names": secret_field_names,
        "masking_mode": masking_mode,
        "type_loaders": type_loaders,
        "nested_resolve_strategy": nested_resolve_strategy,
        "nested_resolve": nested_resolve,
        "config": config,
    }

    if schema is not None:
        # Function mode — throwaway Loader. No cache carries across calls.
        # To cache, construct ``Loader(...)`` explicitly and reuse it.
        if stale_on_error is not None and stale_on_error != "raise":
            logger.warning("stale_on_error has no effect in function mode — keep a Loader instance instead")
        return Loader(*sources, schema=schema, **common_kwargs).load()

    # Decorator mode — the Loader persists for the class lifetime.
    # Cache freshness is keyed on the enabled-source set (which sources are
    # active), not on source content. If an env var changes value between
    # .load() calls but the same sources remain enabled, cached data is
    # returned until the TTL (cache=timedelta(...)) expires or cache=False.
    return Loader.as_decorator(*sources, **common_kwargs)


def _validate_sources(sources: tuple[SourceProtocol, ...]) -> None:
    for source in sources:
        if not isinstance(source, SourceProtocol):
            msg = f"load() positional arguments must be SourceProtocol instances, got {source!r}"
            raise TypeError(msg)

    if not sources:
        msg = "load() requires at least one Source"
        raise TypeError(msg)
