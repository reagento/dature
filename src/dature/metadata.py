from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from dature.loading.resolver import resolve_loader_class
from dature.types import FILE_LIKE_TYPES

if TYPE_CHECKING:
    from dature.field_path import FieldPath
    from dature.protocols import LoaderProtocol, ValidatorProtocol
    from dature.types import (
        DotSeparatedPath,
        ExpandEnvVarsMode,
        FieldMapping,
        FieldMergeCallable,
        FieldValidators,
        FileLike,
        FilePath,
        NameStyle,
    )


# --8<-- [start:type-loader]
@dataclass(frozen=True, slots=True)
class TypeLoader:
    type_: type
    func: Callable[..., Any]


# --8<-- [end:type-loader]


# --8<-- [start:merge-strategy]
class MergeStrategy(StrEnum):
    LAST_WINS = "last_wins"
    FIRST_WINS = "first_wins"
    RAISE_ON_CONFLICT = "raise_on_conflict"


# --8<-- [end:merge-strategy]


# --8<-- [start:field-merge-strategy]
class FieldMergeStrategy(StrEnum):
    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"
    APPEND = "append"
    APPEND_UNIQUE = "append_unique"
    PREPEND = "prepend"
    PREPEND_UNIQUE = "prepend_unique"


# --8<-- [end:field-merge-strategy]


# --8<-- [start:load-metadata]
@dataclass(frozen=True, slots=True, kw_only=True)
class LoadMetadata:
    file_: "FileLike | FilePath | None" = None
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
    type_loaders: "tuple[TypeLoader, ...] | None" = None
    # --8<-- [end:load-metadata]

    def __repr__(self) -> str:
        loader_class = resolve_loader_class(self.loader, self.file_)
        display = loader_class.display_name
        if isinstance(self.file_, FILE_LIKE_TYPES):
            return f"{display} '<stream>'"
        if self.file_ is not None:
            return f"{display} '{self.file_}'"
        return display


# --8<-- [start:merge-rule]
@dataclass(frozen=True, slots=True)
class MergeRule:
    predicate: "FieldPath"
    strategy: "FieldMergeStrategy | FieldMergeCallable"


# --8<-- [end:merge-rule]


# --8<-- [start:field-group]
@dataclass(frozen=True, slots=True)
class FieldGroup:
    fields: "tuple[FieldPath, ...]"

    def __init__(self, *fields: "FieldPath") -> None:
        object.__setattr__(self, "fields", fields)


# --8<-- [end:field-group]


# --8<-- [start:merge-metadata]
@dataclass(frozen=True, slots=True, kw_only=True)
class MergeMetadata:
    sources: tuple[LoadMetadata, ...]
    strategy: MergeStrategy = MergeStrategy.LAST_WINS
    field_merges: tuple[MergeRule, ...] = ()
    field_groups: tuple[FieldGroup, ...] = ()
    skip_broken_sources: bool = False
    skip_invalid_fields: bool = False
    expand_env_vars: "ExpandEnvVarsMode" = "default"
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
    type_loaders: "tuple[TypeLoader, ...] | None" = None


# --8<-- [end:merge-metadata]
