import copy
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING

from dature.config import config
from dature.sources.base import Source

if TYPE_CHECKING:
    from dature.strategies.source import SourceMergeStrategy
    from dature.types import (
        ExpandEnvVarsMode,
        FieldGroupTuple,
        FieldMergeMap,
        MergeStrategyName,
        NestedResolve,
        NestedResolveStrategy,
        SystemConfigDirsArg,
        TypeLoaderMap,
    )


@dataclass(frozen=True, kw_only=True)
class SourceParams:
    """Load-level defaults applied to every Source before loading."""

    expand_env_vars: "ExpandEnvVarsMode | None" = None
    nested_resolve_strategy: "NestedResolveStrategy | None" = None
    nested_resolve: "NestedResolve | None" = None
    search_system_paths: "bool | None" = None
    system_config_dirs: "SystemConfigDirsArg | None" = None


def apply_source_init_params(source: Source, params: SourceParams) -> Source:
    """Inject load-level params into source fields (source > load > config).

    Iterates SourceParams fields by name and matches them against the source's
    dataclass fields. For each matching field currently None: applies
    load-level value, or falls back to config.loading.<same_name> if available.
    """
    source_field_names = {f.name for f in fields(source) if f.init}
    overrides: dict[str, object] = {}

    for f in fields(params):
        name = f.name
        if name not in source_field_names:
            continue
        if getattr(source, name, None) is not None:
            continue  # source-level takes priority
        load_val = getattr(params, name)
        config_val = getattr(config.loading, name, None)
        effective = load_val if load_val is not None else config_val
        if effective is not None:
            overrides[name] = effective

    if not overrides:
        return source

    new_source = copy.copy(source)
    vars(new_source).update(overrides)
    return new_source


@dataclass(slots=True, kw_only=True)
class MergeConfig:
    sources: tuple[Source, ...]
    source_params: SourceParams = field(default_factory=SourceParams)
    strategy: "MergeStrategyName | SourceMergeStrategy" = "last_wins"
    field_merges: "FieldMergeMap | None" = None
    field_groups: "tuple[FieldGroupTuple, ...]" = ()
    skip_broken_sources: bool = False
    skip_invalid_fields: bool = False
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
    type_loaders: "TypeLoaderMap | None" = None

    def __post_init__(self) -> None:
        self.sources = tuple(apply_source_init_params(s, self.source_params) for s in self.sources)
