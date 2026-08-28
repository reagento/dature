import threading
import warnings
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import timedelta
from functools import cache
from types import MappingProxyType
from typing import Any, Literal, TypedDict

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
        "connection_string",
    )
    masking_mode: MaskingMode = "all"


# --8<-- [end:masking-config]


# --8<-- [start:error-display-config]
@dataclass(frozen=True, slots=True)
class ErrorDisplayConfig:
    max_visible_lines: int = 3
    max_line_length: int = 80


# --8<-- [end:error-display-config]


def _default_system_config_dirs() -> Mapping[str, tuple[str, ...]]:
    # A MappingProxyType, not a plain dict: default_config() caches its result process-wide, so
    # every Dature() that doesn't override loading shares this exact mapping instance.
    return MappingProxyType(
        {
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
    )


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


# --8<-- [start:azure-app-config-config]
@dataclass(frozen=True, slots=True)
class AzureAppConfigConfig:
    endpoint: str | None = None
    connection_string: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None


# --8<-- [end:azure-app-config-config]


# --8<-- [start:azure-key-vault-config]
@dataclass(frozen=True, slots=True)
class AzureKeyVaultConfig:
    vault_url: str = ""
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None


# --8<-- [end:azure-key-vault-config]


# --8<-- [start:gcp-secret-manager-config]
@dataclass(frozen=True, slots=True)
class GcpSecretManagerConfig:
    project_id: str = ""
    credentials_file: str | None = None


# --8<-- [end:gcp-secret-manager-config]


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
    azure_app_config: AzureAppConfigConfig = AzureAppConfigConfig()
    azure_key_vault: AzureKeyVaultConfig = AzureKeyVaultConfig()
    gcp_secret_manager: GcpSecretManagerConfig = GcpSecretManagerConfig()


BOOTSTRAP_CONFIG: DatureConfig = DatureConfig()  # pure defaults, never sourced from env


@cache
def default_config() -> DatureConfig:
    """Process-wide env-derived defaults. Computed once, immutable, never mutated.

    ``functools.cache`` holds no lock across the call, so under a race this may run twice —
    that's fine: it is pure with respect to ``os.environ``, returns a frozen dataclass, and
    nothing in the codebase compares configs by identity. Strictly better than the old
    ``RLock``, which serialized *every* config read, not just the first one.
    """
    from dature.field_path import F  # noqa: PLC0415
    from dature.loading.loader import Loader  # noqa: PLC0415
    from dature.sources.env_ import EnvSource  # noqa: PLC0415
    from dature.validators.v import V  # noqa: PLC0415

    return Loader(
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
        config=BOOTSTRAP_CONFIG,
    ).load()


class MaskingOptions(TypedDict, total=False):
    mask: str
    visible_prefix: int
    visible_suffix: int
    min_heuristic_length: int
    heuristic_threshold: float
    secret_field_names: tuple[str, ...]
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


class AzureAppConfigOptions(TypedDict, total=False):
    endpoint: str | None
    connection_string: str | None
    tenant_id: str | None
    client_id: str | None
    client_secret: str | None


class AzureKeyVaultOptions(TypedDict, total=False):
    vault_url: str
    tenant_id: str | None
    client_id: str | None
    client_secret: str | None


class GcpSecretManagerOptions(TypedDict, total=False):
    project_id: str
    credentials_file: str | None


# ---------------------------------------------------------------------------
# Private legacy state — written by the configure() shim, cleared by tests.
# The whole _LegacyState class and legacy singleton are removed in dature 1.5.
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _LegacyState:
    """Process-wide state written by the deprecated ``configure()`` shim. Removed in dature 1.5."""

    override: DatureConfig | None = None
    type_loaders: TypeLoaderMap = field(default_factory=dict)

    def reset(self) -> None:
        self.override = None
        self.type_loaders = {}


legacy = _LegacyState()

# Guards configure()'s read-modify-write of legacy.override/legacy.type_loaders — without it,
# two concurrent configure() calls can read the same base config and one's merged groups clobber
# the other's on write. Not used by resolve_config()/resolve_error_display(): those are plain
# reads of an already-published DatureConfig and need no synchronization. Removed in 1.5 alongside
# configure() itself.
_configure_lock = threading.Lock()


def resolve_config() -> DatureConfig:
    """Resolve the config an internal call site should use when none was passed explicitly.

    During the ``configure()`` deprecation period this honours a process-wide override
    installed via ``configure()``; once that shim is removed in 1.5 this collapses to a
    direct call to ``default_config()``.
    """
    return legacy.override if legacy.override is not None else default_config()


def resolve_error_display() -> ErrorDisplayConfig:
    """Resolve ``ErrorDisplayConfig`` for error rendering, which has no config parameter to thread.

    Falls back to pure defaults while ``default_config()`` has not produced a value yet: the
    bootstrap load renders its own errors through this path, and re-entering ``default_config()``
    from inside its own in-flight call would recurse without bound.  An empty cache means either
    "bootstrap in flight" or "bootstrap failed" — in both cases built-in defaults are the only
    answer available.
    """
    if legacy.override is not None:
        return legacy.override.error_display
    if default_config.cache_info().currsize == 0:
        return BOOTSTRAP_CONFIG.error_display
    return default_config().error_display


def merge_group[D: DataclassInstance](current: D, options: Mapping[str, Any] | None, cls: type[D]) -> D:
    if options is None:
        return current
    if not options:
        return cls()
    # Shallow-copy any mapping-valued override (e.g. LoadingOptions.system_config_dirs): otherwise
    # the built config group would hold the caller's dict by reference, and a mutation the caller
    # makes afterwards would silently change an already-built, supposedly-frozen config.
    safe_options = {name: dict(value) if isinstance(value, Mapping) else value for name, value in options.items()}
    return replace(current, **safe_options)


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
    azure_app_config: AzureAppConfigOptions | None = None,
    azure_key_vault: AzureKeyVaultOptions | None = None,
    gcp_secret_manager: GcpSecretManagerOptions | None = None,
    type_loaders: TypeLoaderMap | None = None,
) -> None:
    # --8<-- [end:configure]
    """Deprecated. Use ``dature.Dature(...)`` instead.

    .. deprecated:: 1.3.0
        ``configure()`` is a backwards-compatibility shim.  It will be removed in dature 1.5.
        Migrate to ``dature.Dature(...)`` — the same group kwargs are accepted.
    """
    from dature._deprecations import CONFIGURE_DEPRECATION_MESSAGE  # noqa: PLC0415

    warnings.warn(CONFIGURE_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)

    with _configure_lock:
        current = resolve_config()

        merged_masking = merge_group(current.masking, masking, MaskingConfig)
        merged_error = merge_group(current.error_display, error_display, ErrorDisplayConfig)
        merged_loading = merge_group(current.loading, loading, LoadingConfig)
        merged_vault = merge_group(current.vault, vault, VaultConfig)
        merged_consul = merge_group(current.consul, consul, ConsulConfig)
        merged_etcd = merge_group(current.etcd, etcd, EtcdConfig)
        merged_ssm = merge_group(current.ssm, ssm, SsmConfig)
        merged_secrets_manager = merge_group(current.secrets_manager, secrets_manager, SecretsManagerConfig)
        merged_azure_app_config = merge_group(current.azure_app_config, azure_app_config, AzureAppConfigConfig)
        merged_azure_key_vault = merge_group(current.azure_key_vault, azure_key_vault, AzureKeyVaultConfig)
        merged_gcp_secret_manager = merge_group(current.gcp_secret_manager, gcp_secret_manager, GcpSecretManagerConfig)

        legacy.override = DatureConfig(
            masking=merged_masking,
            error_display=merged_error,
            loading=merged_loading,
            vault=merged_vault,
            consul=merged_consul,
            etcd=merged_etcd,
            ssm=merged_ssm,
            secrets_manager=merged_secrets_manager,
            azure_app_config=merged_azure_app_config,
            azure_key_vault=merged_azure_key_vault,
            gcp_secret_manager=merged_gcp_secret_manager,
        )
        if type_loaders is not None:
            legacy.type_loaders = type_loaders
