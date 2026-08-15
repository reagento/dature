import threading
import warnings
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import timedelta
from typing import Any, ClassVar, Literal, TypedDict, cast

from dature._deprecations import MASK_SECRETS_DEPRECATION_MESSAGE
from dature.protocols import DataclassInstance
from dature.type_aliases import (
    ExpandEnvVarsMode,
    MaskingMode,
    NestedResolveStrategy,
    StaleOnErrorMode,
    SystemConfigDirsArg,
    TypeLoaderMap,
)


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
        "key",
        "auth",
        "credential",
        "uri",
        "url",
    )
    mask_secrets: bool | None = None
    """Deprecated: use ``masking_mode`` instead. Will be removed in dature 1.3."""
    masking_mode: MaskingMode | None = None
    """``None`` means "not set" — resolved to ``"all"`` by :func:`resolve_masking_mode`."""


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
    cache: bool | timedelta = True
    cache_engine: bool = False
    stale_on_error: StaleOnErrorMode = "keep"
    debug: bool = False
    nested_resolve_strategy: NestedResolveStrategy = "flat"
    expand_env_vars: ExpandEnvVarsMode = "default"
    search_system_paths: bool = True
    system_config_dirs: SystemConfigDirsArg = field(default_factory=_default_system_config_dirs)
    encoding: str | None = None


# --8<-- [end:loading-config]


# --8<-- [start:vault-config]
@dataclass(frozen=True, slots=True)
class VaultConfig:
    host: str = "localhost"
    port: int = 8200
    scheme: Literal["http", "https"] = "http"
    token: str | None = None
    role_id: str | None = None
    secret_id: str | None = None
    namespace: str | None = None
    verify: bool | str = True
    mount_point: str = "secret"
    kv_version: Literal[1, 2] = 2


# --8<-- [end:vault-config]


# --8<-- [start:consul-config]
@dataclass(frozen=True, slots=True)
class ConsulConfig:
    host: str = "localhost"
    port: int = 8500
    scheme: Literal["http", "https"] = "http"
    token: str | None = None
    datacenter: str | None = None
    verify: bool | str = True


# --8<-- [end:consul-config]


# --8<-- [start:etcd-config]
@dataclass(frozen=True, slots=True)
class EtcdConfig:
    host: str = "localhost"
    port: int = 2379
    protocol: Literal["http", "https"] = "http"
    user: str | None = None
    password: str | None = None
    ca_cert: str | None = None
    cert_cert: str | None = None
    cert_key: str | None = None
    timeout: float | None = None


# --8<-- [end:etcd-config]


# --8<-- [start:ssm-config]
@dataclass(frozen=True, slots=True)
class SsmConfig:
    region_name: str = "us-east-1"
    profile_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    endpoint_url: str | None = None


# --8<-- [end:ssm-config]


# --8<-- [start:secrets-manager-config]
@dataclass(frozen=True, slots=True)
class SecretsManagerConfig:
    region_name: str = "us-east-1"
    profile_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    endpoint_url: str | None = None


# --8<-- [end:secrets-manager-config]


@dataclass(frozen=True, slots=True)
class DatureConfig:
    masking: MaskingConfig = MaskingConfig()
    error_display: ErrorDisplayConfig = ErrorDisplayConfig()
    loading: LoadingConfig = LoadingConfig()
    vault: VaultConfig = VaultConfig()
    consul: ConsulConfig = ConsulConfig()
    etcd: EtcdConfig = EtcdConfig()
    ssm: SsmConfig = SsmConfig()
    secrets_manager: SecretsManagerConfig = SecretsManagerConfig()


def _load_config() -> DatureConfig:
    from dature.field_path import F  # noqa: PLC0415
    from dature.main import load  # noqa: PLC0415
    from dature.sources.env_ import EnvSource  # noqa: PLC0415
    from dature.validators.v import V  # noqa: PLC0415

    cfg = load(
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
        cache=False,
    )
    if cfg.masking.mask_secrets is not None:
        warnings.warn(MASK_SECRETS_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
        if cfg.masking.masking_mode is not None:
            # `masking_mode` was set explicitly alongside the deprecated flag — it wins.
            cfg = replace(cfg, masking=replace(cfg.masking, mask_secrets=None))
    return cfg


class MaskingOptions(TypedDict, total=False):
    mask: str
    visible_prefix: int
    visible_suffix: int
    min_heuristic_length: int
    heuristic_threshold: float
    secret_field_names: tuple[str, ...]
    mask_secrets: bool | None
    masking_mode: MaskingMode


class ErrorDisplayOptions(TypedDict, total=False):
    max_visible_lines: int
    max_line_length: int


class LoadingOptions(TypedDict, total=False):
    cache: bool | timedelta
    cache_engine: bool
    stale_on_error: StaleOnErrorMode
    debug: bool
    nested_resolve_strategy: NestedResolveStrategy
    expand_env_vars: ExpandEnvVarsMode
    search_system_paths: bool
    system_config_dirs: SystemConfigDirsArg
    encoding: str | None


class VaultOptions(TypedDict, total=False):
    host: str
    port: int
    scheme: Literal["http", "https"]
    token: str | None
    role_id: str | None
    secret_id: str | None
    namespace: str | None
    verify: bool | str
    mount_point: str
    kv_version: Literal[1, 2]


class ConsulOptions(TypedDict, total=False):
    host: str
    port: int
    scheme: Literal["http", "https"]
    token: str | None
    datacenter: str | None
    verify: bool | str


class EtcdOptions(TypedDict, total=False):
    host: str
    port: int
    protocol: Literal["http", "https"]
    user: str | None
    password: str | None
    ca_cert: str | None
    cert_cert: str | None
    cert_key: str | None
    timeout: float | None


class SsmOptions(TypedDict, total=False):
    region_name: str
    profile_name: str | None
    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    aws_session_token: str | None
    endpoint_url: str | None


class SecretsManagerOptions(TypedDict, total=False):
    region_name: str
    profile_name: str | None
    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    aws_session_token: str | None
    endpoint_url: str | None


_config_lock: threading.RLock = threading.RLock()


class _ConfigProxy:
    _instance: DatureConfig | None = None
    _loading: bool = False
    _type_loaders: ClassVar[TypeLoaderMap] = {}

    @staticmethod
    def ensure_loaded() -> DatureConfig:
        with _config_lock:
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
        with _config_lock:
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
    def vault(self) -> VaultConfig:
        return self.ensure_loaded().vault

    @property
    def consul(self) -> ConsulConfig:
        return self.ensure_loaded().consul

    @property
    def etcd(self) -> EtcdConfig:
        return self.ensure_loaded().etcd

    @property
    def ssm(self) -> SsmConfig:
        return self.ensure_loaded().ssm

    @property
    def secrets_manager(self) -> SecretsManagerConfig:
        return self.ensure_loaded().secrets_manager

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
def configure(  # noqa: PLR0913
    *,
    masking: MaskingOptions | None = None,
    error_display: ErrorDisplayOptions | None = None,
    loading: LoadingOptions | None = None,
    vault: VaultOptions | None = None,
    consul: ConsulOptions | None = None,
    etcd: EtcdOptions | None = None,
    ssm: SsmOptions | None = None,
    secrets_manager: SecretsManagerOptions | None = None,
    type_loaders: TypeLoaderMap | None = None,
) -> None:
    # --8<-- [end:configure]
    with _config_lock:
        current = config.ensure_loaded()

        if masking is not None and "mask_secrets" in masking:
            warnings.warn(MASK_SECRETS_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)

        merged_masking = _merge_group(current.masking, masking, MaskingConfig)
        if masking is not None and "mask_secrets" in masking and "masking_mode" in masking:
            merged_masking = replace(merged_masking, mask_secrets=None)
        merged_error = _merge_group(current.error_display, error_display, ErrorDisplayConfig)
        merged_loading = _merge_group(current.loading, loading, LoadingConfig)
        merged_vault = _merge_group(current.vault, vault, VaultConfig)
        merged_consul = _merge_group(current.consul, consul, ConsulConfig)
        merged_etcd = _merge_group(current.etcd, etcd, EtcdConfig)
        merged_ssm = _merge_group(current.ssm, ssm, SsmConfig)
        merged_secrets_manager = _merge_group(current.secrets_manager, secrets_manager, SecretsManagerConfig)

        config.set_instance(
            DatureConfig(
                masking=merged_masking,
                error_display=merged_error,
                loading=merged_loading,
                vault=merged_vault,
                consul=merged_consul,
                etcd=merged_etcd,
                ssm=merged_ssm,
                secrets_manager=merged_secrets_manager,
            ),
        )
        if type_loaders is not None:
            config.set_type_loaders(type_loaders)
