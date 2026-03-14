from collections.abc import Callable
from pathlib import Path
from typing import Any, overload

from dature.config import config
from dature.loading.multi import merge_load_as_function, merge_make_decorator
from dature.loading.resolver import resolve_loader
from dature.loading.single import load_as_function, make_decorator
from dature.metadata import LoadMetadata, MergeMetadata
from dature.protocols import DataclassInstance
from dature.types import FILE_LIKE_TYPES, FileOrStream


@overload
def load[T](
    metadata: LoadMetadata | MergeMetadata | tuple[LoadMetadata, ...] | None,
    /,
    dataclass_: type[T],
    *,
    debug: bool | None = None,
) -> T: ...


@overload
def load(
    metadata: LoadMetadata | MergeMetadata | tuple[LoadMetadata, ...] | None = None,
    /,
    dataclass_: None = None,
    *,
    cache: bool | None = None,
    debug: bool | None = None,
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]: ...


# --8<-- [start:load]
def load(
    metadata: LoadMetadata | MergeMetadata | tuple[LoadMetadata, ...] | None = None,
    /,
    dataclass_: type[Any] | None = None,
    *,
    cache: bool | None = None,
    debug: bool | None = None,
) -> Any:
    # --8<-- [end:load]
    if cache is None:
        cache = config.loading.cache
    if debug is None:
        debug = config.loading.debug

    if isinstance(metadata, tuple):
        metadata = MergeMetadata(sources=metadata)

    if isinstance(metadata, MergeMetadata):
        merge_type_loaders = (metadata.type_loaders or ()) + config.type_loaders
        if dataclass_ is not None:
            return merge_load_as_function(metadata, dataclass_, debug=debug, type_loaders=merge_type_loaders)
        return merge_make_decorator(metadata, cache=cache, debug=debug, type_loaders=merge_type_loaders)

    if metadata is None:
        metadata = LoadMetadata()

    type_loaders = (metadata.type_loaders or ()) + config.type_loaders
    loader_instance = resolve_loader(metadata, type_loaders=type_loaders)

    file_or_path: FileOrStream
    if isinstance(metadata.file_, FILE_LIKE_TYPES):
        file_or_path = metadata.file_
    elif metadata.file_ is not None:
        file_or_path = Path(metadata.file_)
    else:
        file_or_path = Path()

    if dataclass_ is not None:
        return load_as_function(
            loader_instance=loader_instance,
            file_path=file_or_path,
            dataclass_=dataclass_,
            metadata=metadata,
            debug=debug,
        )

    return make_decorator(
        loader_instance=loader_instance,
        file_path=file_or_path,
        metadata=metadata,
        cache=cache,
        debug=debug,
    )
