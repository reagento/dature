from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dature.merging.strategy import MergeStrategyEnum
from dature.sources.base import Source

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from dature.types import (
        ExpandEnvVarsMode,
        FieldGroupTuple,
        FieldMergeMap,
        NestedResolve,
        NestedResolveStrategy,
        TypeLoaderMap,
    )


@dataclass(frozen=True, kw_only=True)
class SourceParams:
    """Load-level defaults applied to every Source before loading."""

    expand_env_vars: "ExpandEnvVarsMode | None" = None
    nested_resolve_strategy: "NestedResolveStrategy | None" = None
    nested_resolve: "NestedResolve | None" = None
    search_system_paths: "bool | None" = None
    system_config_dirs: "Iterable[Path] | None" = None


@dataclass(slots=True, kw_only=True)
class MergeConfig:
    sources: tuple[Source, ...]
    source_params: SourceParams = field(default_factory=SourceParams)
    strategy: MergeStrategyEnum = MergeStrategyEnum.LAST_WINS
    field_merges: "FieldMergeMap | None" = None
    field_groups: "tuple[FieldGroupTuple, ...]" = ()
    skip_broken_sources: bool = False
    skip_invalid_fields: bool = False
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
    type_loaders: "TypeLoaderMap | None" = None
