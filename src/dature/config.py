from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict, cast

from dature.types import ExpandEnvVarsMode, NestedResolveStrategy, SystemConfigDirsArg, TypeLoaderMap

if TYPE_CHECKING:
    from dature.protocols import DataclassInstance


# --8<-- [start:masking-config]
@dataclass(frozen=True, slots=True)
class MaskingConfig:
    mask: str = "<REDACTED>"
    visible_prefix: int = 0
    visible_suffix: int = 0
    min_heuristic_length: int = 8
    heuristic_threshold: float = 0.5
    secret_field_names: tuple[str, ...] = (
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "api_secret",
        "access_key",
        "private_key",
        "auth",
        "credential",
    )
    mask_secrets: bool = True


# --8<-- [end:masking-config]


# --8<-- [start:error-display-config]
@dataclass(frozen=True, slots=True)
class ErrorDisplayConfig:
    max_visible_lines: int = 3
    max_line_length: int = 80


# --8<-- [end:error-display-config]


def _default_system_config_dirs() -> dict[str, tuple[str, ...]]:
    return {
        "linux": (
            "${XDG_CONFIG_HOME:-$HOME/.config}",
            "/etc",
            "${XDG_CONFIG_DIRS:-/etc/xdg}",
        ),
        "darwin": (
            "$HOME/Library/Application Support",
            "${XDG_CONFIG_HOME:-$HOME/.config}",
            "/etc",
            "${XDG_CONFIG_DIRS:-/etc/xdg}",
        ),
        "win32": ("$APPDATA",),
    }


# --8<-- [start:loading-config]
@dataclass(frozen=True, slots=True)
class LoadingConfig:
    cache: bool = True
    debug: bool = False
    nested_resolve_strategy: NestedResolveStrategy = "flat"
    expand_env_vars: ExpandEnvVarsMode = "default"
    search_system_paths: bool = True
    system_config_dirs: SystemConfigDirsArg = field(default_factory=_default_system_config_dirs)


# --8<-- [end:loading-config]


@dataclass(frozen=True, slots=True)
class DatureConfig:
    masking: MaskingConfig = MaskingConfig()
    error_display: ErrorDisplayConfig = ErrorDisplayConfig()
    loading: LoadingConfig = LoadingConfig()


def _load_config() -> DatureConfig:
    from dature.field_path import F  # noqa: PLC0415
    from dature.main import load  # noqa: PLC0415
    from dature.sources.env_ import EnvSource  # noqa: PLC0415
    from dature.validators.v import V  # noqa: PLC0415

    return load(
        EnvSource(
            prefix="DATURE_",
            validators={
                F[DatureConfig].masking.mask: V.len() >= 1,
                F[DatureConfig].masking.visible_prefix: V >= 0,
                F[DatureConfig].masking.visible_suffix: V >= 0,
                F[DatureConfig].masking.min_heuristic_length: V >= 1,
                F[DatureConfig].error_display.max_visible_lines: V >= 1,
                F[DatureConfig].error_display.max_line_length: V >= 1,
            },
        ),
        schema=DatureConfig,
    )


class MaskingOptions(TypedDict, total=False):
    mask: str
    visible_prefix: int
    visible_suffix: int
    min_heuristic_length: int
    heuristic_threshold: float
    secret_field_names: tuple[str, ...]
    mask_secrets: bool


class ErrorDisplayOptions(TypedDict, total=False):
    max_visible_lines: int
    max_line_length: int


class LoadingOptions(TypedDict, total=False):
    cache: bool
    debug: bool
    nested_resolve_strategy: NestedResolveStrategy
    expand_env_vars: ExpandEnvVarsMode
    search_system_paths: bool
    system_config_dirs: SystemConfigDirsArg


class _ConfigProxy:
    _instance: DatureConfig | None = None
    _loading: bool = False
    _type_loaders: ClassVar[TypeLoaderMap] = {}

    @staticmethod
    def ensure_loaded() -> DatureConfig:
        if _ConfigProxy._instance is not None:
            return _ConfigProxy._instance
        if _ConfigProxy._loading:
            return DatureConfig()
        _ConfigProxy._loading = True
        try:
            _ConfigProxy._instance = _load_config()
        finally:
            _ConfigProxy._loading = False
        return _ConfigProxy._instance

    @staticmethod
    def set_instance(value: DatureConfig | None) -> None:
        _ConfigProxy._instance = value

    @staticmethod
    def set_type_loaders(value: TypeLoaderMap) -> None:
        _ConfigProxy._type_loaders = value

    @property
    def masking(self) -> MaskingConfig:
        return self.ensure_loaded().masking

    @property
    def error_display(self) -> ErrorDisplayConfig:
        return self.ensure_loaded().error_display

    @property
    def loading(self) -> LoadingConfig:
        return self.ensure_loaded().loading

    @property
    def type_loaders(self) -> TypeLoaderMap:
        return _ConfigProxy._type_loaders


config: _ConfigProxy = _ConfigProxy()


def _merge_group[D: DataclassInstance](current: D, options: Mapping[str, Any] | None, cls: type[D]) -> D:
    if options is None:
        return current
    if not options:
        return cls()
    return cls(**cast("dict[str, Any]", asdict(current) | dict(options)))


# --8<-- [start:configure]
def configure(
    *,
    masking: MaskingOptions | None = None,
    error_display: ErrorDisplayOptions | None = None,
    loading: LoadingOptions | None = None,
    type_loaders: TypeLoaderMap | None = None,
) -> None:
    # --8<-- [end:configure]
    current = config.ensure_loaded()

    merged_masking = _merge_group(current.masking, masking, MaskingConfig)
    merged_error = _merge_group(current.error_display, error_display, ErrorDisplayConfig)
    merged_loading = _merge_group(current.loading, loading, LoadingConfig)

    config.set_instance(
        DatureConfig(
            masking=merged_masking,
            error_display=merged_error,
            loading=merged_loading,
        ),
    )
    if type_loaders is not None:
        config.set_type_loaders(type_loaders)
