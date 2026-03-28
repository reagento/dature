from collections.abc import Callable
from pathlib import Path
from typing import Any, overload

from dature.config import config
from dature.loading.multi import merge_load_as_function, merge_make_decorator
from dature.loading.resolver import resolve_loader
from dature.loading.single import load_as_function, make_decorator
from dature.metadata import Merge, Source
from dature.protocols import DataclassInstance
from dature.types import FILE_LIKE_TYPES, FileOrStream


@overload
def load[T](
    metadata: Source | Merge | tuple[Source, ...] | None,
    /,
    dataclass_: type[T],
    *,
    debug: bool | None = None,
) -> T: ...


@overload
def load(
    metadata: Source | Merge | tuple[Source, ...] | None = None,
    /,
    dataclass_: None = None,
    *,
    cache: bool | None = None,
    debug: bool | None = None,
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]: ...


# --8<-- [start:load]
def load(
    metadata: Source | Merge | tuple[Source, ...] | None = None,
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
        metadata = Merge(*metadata)

    if isinstance(metadata, Merge):
        merge_type_loaders = (metadata.type_loaders or ()) + config.type_loaders
        if dataclass_ is not None:
            return merge_load_as_function(metadata, dataclass_, debug=debug, type_loaders=merge_type_loaders)
        return merge_make_decorator(metadata, cache=cache, debug=debug, type_loaders=merge_type_loaders)

    if metadata is None:
        metadata = Source()

    type_loaders = (metadata.type_loaders or ()) + config.type_loaders
    loader_instance = resolve_loader(
        metadata,
        type_loaders=type_loaders,
        nested_resolve_strategy=config.loading.nested_resolve_strategy,
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
