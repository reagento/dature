import logging
from collections.abc import Callable
from typing import Any, overload

from dature.config import config
from dature.loading.merge_config import MergeConfig
from dature.loading.multi import merge_load_as_function, merge_make_decorator
from dature.loading.single import load_as_function, make_decorator
from dature.merging.strategy import MergeStrategyEnum
from dature.protocols import DataclassInstance
from dature.sources.base import Source
from dature.types import (
    ExpandEnvVarsMode,
    FieldGroupTuple,
    FieldMergeMap,
    MergeStrategyName,
    NestedResolve,
    NestedResolveStrategy,
    TypeLoaderMap,
)

logger = logging.getLogger("dature")


@overload
def load[T](
    *sources: Source,
    schema: type[T],
    debug: bool | None = None,
    strategy: MergeStrategyName = "last_wins",
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
) -> T: ...


@overload
def load(
    *sources: Source,
    schema: None = None,
    cache: bool | None = None,
    debug: bool | None = None,
    strategy: MergeStrategyName = "last_wins",
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
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]: ...


# --8<-- [start:load]
def load(  # noqa: PLR0913
    *sources: Source,
    schema: type[Any] | None = None,
    cache: bool | None = None,
    debug: bool | None = None,
    strategy: MergeStrategyName = "last_wins",
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
) -> Any:
    # --8<-- [end:load]
    if cache is None:
        cache = config.loading.cache
    if debug is None:
        debug = config.loading.debug

    _validate_sources(sources)

    if len(sources) == 1 and (
        strategy != "last_wins"
        or field_merges is not None
        or field_groups != ()
        or skip_broken_sources
        or skip_invalid_fields
    ):
        logger.warning("Merge-related parameters have no effect with a single source")

    if len(sources) > 1:
        return _load_multi(
            sources=sources,
            schema=schema,
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

    source = sources[0]

    if schema is not None:
        return load_as_function(
            source=source,
            schema=schema,
            debug=debug,
            secret_field_names=secret_field_names,
            mask_secrets=mask_secrets,
            expand_env_vars=expand_env_vars,
            type_loaders=type_loaders,
            nested_resolve_strategy=nested_resolve_strategy,
            nested_resolve=nested_resolve,
        )

    return make_decorator(
        source=source,
        cache=cache,
        debug=debug,
        secret_field_names=secret_field_names,
        mask_secrets=mask_secrets,
        expand_env_vars=expand_env_vars,
        type_loaders=type_loaders,
        nested_resolve_strategy=nested_resolve_strategy,
        nested_resolve=nested_resolve,
    )


def _validate_sources(sources: tuple[Source, ...]) -> None:
    for source in sources:
        if not isinstance(source, Source):
            msg = f"load() positional arguments must be Source instances, got {source!r}"
            raise TypeError(msg)

    if not sources:
        msg = "load() requires at least one Source"
        raise TypeError(msg)


def _load_multi(  # noqa: PLR0913
    *,
    sources: tuple[Source, ...],
    schema: type[DataclassInstance] | None,
    cache: bool,
    debug: bool,
    strategy: MergeStrategyName,
    field_merges: FieldMergeMap | None,
    field_groups: tuple[FieldGroupTuple, ...],
    skip_broken_sources: bool,
    skip_invalid_fields: bool,
    expand_env_vars: ExpandEnvVarsMode | None,
    secret_field_names: tuple[str, ...] | None,
    mask_secrets: bool | None,
    type_loaders: TypeLoaderMap | None,
    nested_resolve_strategy: NestedResolveStrategy | None,
    nested_resolve: NestedResolve | None,
) -> DataclassInstance | Callable[[type[DataclassInstance]], type[DataclassInstance]]:
    merge_meta = MergeConfig(
        sources=sources,
        strategy=MergeStrategyEnum(strategy),
        field_merges=field_merges,
        field_groups=field_groups,
        skip_broken_sources=skip_broken_sources,
        skip_invalid_fields=skip_invalid_fields,
        expand_env_vars=expand_env_vars or "default",
        secret_field_names=secret_field_names,
        mask_secrets=mask_secrets,
        type_loaders=type_loaders,
        nested_resolve_strategy=nested_resolve_strategy,
        nested_resolve=nested_resolve,
    )
    if schema is not None:
        return merge_load_as_function(merge_meta, schema, debug=debug)
    return merge_make_decorator(merge_meta, cache=cache, debug=debug)
