from dataclasses import dataclass
from typing import TYPE_CHECKING

from dature.merging.strategy import MergeStrategyEnum
from dature.sources.base import Source

if TYPE_CHECKING:
    from dature.types import (
        ExpandEnvVarsMode,
        FieldGroupTuple,
        FieldMergeMap,
        NestedResolve,
        NestedResolveStrategy,
        TypeLoaderMap,
    )


@dataclass(slots=True, kw_only=True)
class MergeConfig:
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
