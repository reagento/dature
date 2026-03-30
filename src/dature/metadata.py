from pathlib import Path
from typing import TYPE_CHECKING

from dature.expansion.env_expand import expand_file_path
from dature.loading.resolver import resolve_loader_class
from dature.types import FILE_LIKE_TYPES

if TYPE_CHECKING:
    from dature.field_path import FieldPath
    from dature.protocols import LoaderProtocol, ValidatorProtocol
    from dature.types import (
        DotSeparatedPath,
        ExpandEnvVarsMode,
        FieldGroupTuple,
        FieldMapping,
        FieldMergeMap,
        FieldValidators,
        FileLike,
        FilePath,
        NameStyle,
        NestedResolve,
        NestedResolveStrategy,
        TypeLoaderMap,
    )

from dataclasses import dataclass

from dature.merging.strategy import MergeStrategyEnum


# --8<-- [start:load-metadata]
@dataclass(slots=True, kw_only=True)
class Source:
    file: "FileLike | FilePath | None" = None
    loader: "type[LoaderProtocol] | None" = None
    prefix: "DotSeparatedPath | None" = None
    split_symbols: str = "__"
    name_style: "NameStyle | None" = None
    field_mapping: "FieldMapping | None" = None
    root_validators: "tuple[ValidatorProtocol, ...] | None" = None
    validators: "FieldValidators | None" = None
    expand_env_vars: "ExpandEnvVarsMode | None" = None
    skip_if_broken: bool | None = None
    skip_if_invalid: "bool | tuple[FieldPath, ...] | None" = None
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
    type_loaders: "TypeLoaderMap | None" = None
    nested_resolve_strategy: "NestedResolveStrategy | None" = None
    nested_resolve: "NestedResolve | None" = None
    # --8<-- [end:load-metadata]

    def __post_init__(self) -> None:
        if isinstance(self.file, (str, Path)):
            self.file = expand_file_path(str(self.file), mode="strict")

    def __repr__(self) -> str:
        loader_class = resolve_loader_class(self.loader, self.file)
        display = loader_class.display_name
        if isinstance(self.file, FILE_LIKE_TYPES):
            return f"{display} '<stream>'"
        if self.file is not None:
            return f"{display} '{self.file}'"
        return display


@dataclass(slots=True, kw_only=True)
class _MergeConfig:
    sources: tuple[Source, ...]
    strategy: MergeStrategyEnum = MergeStrategyEnum.LAST_WINS
    field_merges: "FieldMergeMap | None" = None
    field_groups: "tuple[FieldGroupTuple, ...]" = ()
    skip_broken_sources: bool = False
    skip_invalid_fields: bool = False
    expand_env_vars: "ExpandEnvVarsMode" = "default"
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
    type_loaders: "TypeLoaderMap | None" = None
    nested_resolve_strategy: "NestedResolveStrategy | None" = None
    nested_resolve: "NestedResolve | None" = None
