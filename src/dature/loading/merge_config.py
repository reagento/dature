import copy
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, TypeVar

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

TSource = TypeVar("TSource", bound=Source)


@dataclass(frozen=True, kw_only=True)
class SourceParams:
    """Load-level defaults applied to every Source before loading."""

    expand_env_vars: "ExpandEnvVarsMode | None" = None
    nested_resolve_strategy: "NestedResolveStrategy | None" = None
    nested_resolve: "NestedResolve | None" = None
    search_system_paths: "bool | None" = None
    system_config_dirs: "SystemConfigDirsArg | None" = None


def apply_source_init_params[T: Source](source: T, params: SourceParams) -> T:
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
    new_dict = vars(new_source)
    new_dict.update(overrides)
    # `FileFieldMixin._resolved_file_path` is a cached_property whose value lives in
    # `__dict__`; drop it so it re-resolves against the overridden inputs
    # (search_system_paths, system_config_dirs) instead of returning a stale result.
    new_dict.pop("_resolved_file_path", None)
    return new_source


def apply_source_config_defaults[T: Source](source: T) -> T:
    """Fill None-valued source fields from ``dature.config.<source.config_group>``.

    Sources whose connection/credential params are typically configured globally
    (e.g. ``VaultSource`` → ``config.vault``) opt in via the ClassVar
    ``config_group``. Source-level non-None values always win; this only fills gaps.
    No-op when ``source.config_group`` is ``None`` (the default).
    Order: instance > load-level (apply_source_init_params) > config group (this).
    """
    group_name: str | None = getattr(type(source), "config_group", None)
    if group_name is None:
        return source

    cfg_group = getattr(config, group_name, None)
    if cfg_group is None:
        return source

    source_field_names = {f.name for f in fields(source) if f.init}
    overrides: dict[str, object] = {}
    for f in fields(cfg_group):
        name = f.name
        if name not in source_field_names:
            continue
        if getattr(source, name, None) is not None:
            continue  # source-level wins
        cfg_val = getattr(cfg_group, name)
        if cfg_val is not None:
            overrides[name] = cfg_val

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
        prepared: list[Source] = []
        for s in self.sources:
            merged = apply_source_config_defaults(apply_source_init_params(s, self.source_params))
            merged._validate()  # noqa: SLF001
            prepared.append(merged)
        self.sources = tuple(prepared)
