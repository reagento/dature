from collections.abc import Callable
from pathlib import Path
from typing import Any, overload

from dature.config import config
from dature.loading.multi import merge_load_as_function, merge_make_decorator
from dature.loading.resolver import resolve_loader
from dature.loading.single import load_as_function, make_decorator
from dature.metadata import (
    FieldGroup,
    MergeRule,
    MergeStrategy,
    Source,
    TypeLoader,
    _MergeConfig,
)
from dature.protocols import DataclassInstance
from dature.types import FILE_LIKE_TYPES, ExpandEnvVarsMode, FileOrStream, NestedResolve, NestedResolveStrategy


@overload
def load[T](
    *sources: Source,
    dataclass_: type[T],
    debug: bool | None = None,
    strategy: MergeStrategy = MergeStrategy.LAST_WINS,
    field_merges: tuple[MergeRule, ...] = (),
    field_groups: tuple[FieldGroup, ...] = (),
    skip_broken_sources: bool = False,
    skip_invalid_fields: bool = False,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    secret_field_names: tuple[str, ...] | None = None,
    mask_secrets: bool | None = None,
    type_loaders: tuple[TypeLoader, ...] | None = None,
    nested_resolve_strategy: NestedResolveStrategy | None = None,
    nested_resolve: NestedResolve | None = None,
) -> T: ...


@overload
def load(
    *sources: Source,
    dataclass_: None = None,
    cache: bool | None = None,
    debug: bool | None = None,
    strategy: MergeStrategy = MergeStrategy.LAST_WINS,
    field_merges: tuple[MergeRule, ...] = (),
    field_groups: tuple[FieldGroup, ...] = (),
    skip_broken_sources: bool = False,
    skip_invalid_fields: bool = False,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    secret_field_names: tuple[str, ...] | None = None,
    mask_secrets: bool | None = None,
    type_loaders: tuple[TypeLoader, ...] | None = None,
    nested_resolve_strategy: NestedResolveStrategy | None = None,
    nested_resolve: NestedResolve | None = None,
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]: ...


# --8<-- [start:load]
def load(  # noqa: PLR0913
    *sources: Source,
    dataclass_: type[Any] | None = None,
    cache: bool | None = None,
    debug: bool | None = None,
    strategy: MergeStrategy = MergeStrategy.LAST_WINS,
    field_merges: tuple[MergeRule, ...] = (),
    field_groups: tuple[FieldGroup, ...] = (),
    skip_broken_sources: bool = False,
    skip_invalid_fields: bool = False,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    secret_field_names: tuple[str, ...] | None = None,
    mask_secrets: bool | None = None,
    type_loaders: tuple[TypeLoader, ...] | None = None,
    nested_resolve_strategy: NestedResolveStrategy | None = None,
    nested_resolve: NestedResolve | None = None,
) -> Any:
    # --8<-- [end:load]
    if cache is None:
        cache = config.loading.cache
    if debug is None:
        debug = config.loading.debug

    if len(sources) > 1:
        merge_meta = _MergeConfig(
            sources=sources,
            strategy=strategy,
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
        merge_type_loaders = (merge_meta.type_loaders or ()) + config.type_loaders
        if dataclass_ is not None:
            return merge_load_as_function(merge_meta, dataclass_, debug=debug, type_loaders=merge_type_loaders)
        return merge_make_decorator(merge_meta, cache=cache, debug=debug, type_loaders=merge_type_loaders)

    if not sources:
        msg = "load() requires at least one Source"
        raise TypeError(msg)

    metadata = sources[0]

    source_type_loaders = (metadata.type_loaders or ()) + (type_loaders or ()) + config.type_loaders
    loader_instance = resolve_loader(
        metadata,
        expand_env_vars=expand_env_vars,
        type_loaders=source_type_loaders,
        nested_resolve_strategy=nested_resolve_strategy or config.loading.nested_resolve_strategy,
        nested_resolve=nested_resolve,
    )

    fileor_path: FileOrStream
    if isinstance(metadata.file, FILE_LIKE_TYPES):
        fileor_path = metadata.file
    elif metadata.file is not None:
        fileor_path = Path(metadata.file)
    else:
        fileor_path = Path()

    if dataclass_ is not None:
        return load_as_function(
            loader_instance=loader_instance,
            file_path=fileor_path,
            dataclass_=dataclass_,
            metadata=metadata,
            debug=debug,
        )

    return make_decorator(
        loader_instance=loader_instance,
        file_path=fileor_path,
        metadata=metadata,
        cache=cache,
        debug=debug,
    )
