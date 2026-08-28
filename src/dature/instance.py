"""``Dature`` — the explicit, immutable config instance.

Use ``Dature(...)`` instead of ``configure()`` to override env-derived defaults.
Each instance is independent: creating a new one with different parameters does
not affect other instances or the process-wide defaults.

Configuration binds at **construction time** (or, in decorator mode, at
**decoration / import time**).  This means:

- Two ``Dature`` instances with different ``masking=`` settings each apply their
  own masking, independently.
- In decorator mode (``@conf.load(...)``), the config is frozen when Python
  imports the decorated class — not lazily on each ``Settings()`` call.  If you
  need config to be determined at call time, use ``conf.load(..., schema=...)``
  in function mode instead.

Migration from ``configure()``:

.. code-block:: python

   # Before:
   dature.configure(vault={"host": "vault.internal"})
   result = dature.load(VaultSource(path="secrets"), schema=Settings)

   # After:
   conf = dature.Dature(vault={"host": "vault.internal"})
   result = conf.load(VaultSource(path="secrets"), schema=Settings)
"""

# keep in sync with main.load overloads and Loader.as_decorator signature
from collections.abc import Callable, Iterable, Sequence
from dataclasses import fields
from datetime import timedelta
from typing import Any, overload

from dature.config import (
    AzureAppConfigConfig,
    AzureAppConfigOptions,
    AzureKeyVaultConfig,
    AzureKeyVaultOptions,
    ConsulConfig,
    ConsulOptions,
    DatureConfig,
    ErrorDisplayConfig,
    ErrorDisplayOptions,
    EtcdConfig,
    EtcdOptions,
    GcpSecretManagerConfig,
    GcpSecretManagerOptions,
    LoadingConfig,
    LoadingOptions,
    MaskingConfig,
    MaskingOptions,
    SecretsManagerConfig,
    SecretsManagerOptions,
    SsmConfig,
    SsmOptions,
    VaultConfig,
    VaultOptions,
    default_config,
    merge_group,
)
from dature.loading.loader import Loader
from dature.loading.merge_runtime import SourceMergeStrategy
from dature.main import DEFAULT_STRATEGY, dispatch
from dature.masking.detection import matches_secret_name
from dature.protocols import DataclassInstance
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import (
    ExpandEnvVarsMode,
    FieldGroupTuple,
    FieldMergeMap,
    MaskingMode,
    MergeStrategyName,
    NestedResolve,
    NestedResolveStrategy,
    SkipFieldsInvalid,
    StaleOnErrorMode,
    TypeLoaderMap,
)
from dature.validators.root import RootPredicate

_CONFIG_GROUP_NAMES = tuple(f.name for f in fields(DatureConfig))


# --8<-- [start:dature-init]
class Dature:
    """Explicit, immutable dature configuration instance.

    All parameters are optional and merge on top of the process-wide
    ``DATURE_*``-derived defaults (``default_config()``).  Omitting a group
    inherits the env default; passing ``{}`` resets it to built-in defaults;
    passing ``{"key": value}`` overrides individual fields.

    Args:
        masking: Masking configuration overrides (mask string, visible
            prefix/suffix, heuristic thresholds, etc.).
        error_display: Error-rendering overrides (max visible lines, max line
            length) for this instance's exceptions.
        loading: Loading behaviour overrides (cache, debug, expand_env_vars, …).
        vault: Vault connection overrides.
        consul: Consul connection overrides.
        etcd: Etcd connection overrides.
        ssm: AWS SSM connection overrides.
        secrets_manager: AWS Secrets Manager connection overrides.
        azure_app_config: Azure App Configuration connection overrides.
        azure_key_vault: Azure Key Vault connection overrides.
        gcp_secret_manager: GCP Secret Manager connection overrides.
        type_loaders: Extra type loaders merged with load-level and source-level
            ones.  Priority: ``Dature`` < load-level < source.
    """

    def __init__(  # noqa: PLR0913
        self,
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
        base = default_config()
        self._config = DatureConfig(
            masking=merge_group(base.masking, masking, MaskingConfig),
            error_display=merge_group(base.error_display, error_display, ErrorDisplayConfig),
            loading=merge_group(base.loading, loading, LoadingConfig),
            vault=merge_group(base.vault, vault, VaultConfig),
            consul=merge_group(base.consul, consul, ConsulConfig),
            etcd=merge_group(base.etcd, etcd, EtcdConfig),
            ssm=merge_group(base.ssm, ssm, SsmConfig),
            secrets_manager=merge_group(base.secrets_manager, secrets_manager, SecretsManagerConfig),
            azure_app_config=merge_group(base.azure_app_config, azure_app_config, AzureAppConfigConfig),
            azure_key_vault=merge_group(base.azure_key_vault, azure_key_vault, AzureKeyVaultConfig),
            gcp_secret_manager=merge_group(base.gcp_secret_manager, gcp_secret_manager, GcpSecretManagerConfig),
        )
        self._type_loaders: TypeLoaderMap | None = dict(type_loaders) if type_loaders is not None else None

    # --8<-- [end:dature-init]

    @classmethod
    def _from_config(cls, config: DatureConfig, type_loaders: TypeLoaderMap | None) -> "Dature":
        """Build an instance from an already-merged config, bypassing env re-resolution."""
        instance = object.__new__(cls)
        instance._config = config  # noqa: SLF001
        instance._type_loaders = dict(type_loaders) if type_loaders is not None else None  # noqa: SLF001
        return instance

    @property
    def config(self) -> DatureConfig:
        """The effective ``DatureConfig`` for this instance (frozen, introspectable)."""
        return self._config

    def replace(self, **groups: Any) -> "Dature":  # noqa: ANN401
        """Return a new ``Dature`` instance with the given groups overridden.

        All other groups are inherited from this instance's config, NOT from
        ``default_config()`` — making this a diff on top of the current instance.

        Example::

            base = Dature(vault={"host": "vault.internal"})
            debug_version = base.replace(loading={"debug": True})

        Raises:
            TypeError: If *groups* contains a name that is not a config group name
                or ``type_loaders``.
        """
        unknown = set(groups) - {*_CONFIG_GROUP_NAMES, "type_loaders"}
        if unknown:
            msg = f"Unknown config group(s): {', '.join(sorted(unknown))}"
            raise TypeError(msg)

        merged = {}
        for name in _CONFIG_GROUP_NAMES:
            current = getattr(self._config, name)
            merged[name] = merge_group(current, groups.get(name), type(current))
        type_loaders = groups.get("type_loaders", self._type_loaders)
        return Dature._from_config(DatureConfig(**merged), type_loaders)

    # keep in sync with main.load overloads
    @overload
    def load[T: DataclassInstance](
        self,
        *sources: SourceProtocol,
        schema: type[T],
        cache: bool | timedelta | None = None,
        cache_engine: bool | None = None,
        stale_on_error: StaleOnErrorMode | None = None,
        debug: bool | None = None,
        strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
        field_merges: FieldMergeMap | None = None,
        field_groups: Sequence[FieldGroupTuple] = (),
        root_validators: Iterable[RootPredicate] = (),
        skip_if_broken: bool = False,
        skip_if_missing: bool = False,
        skip_field_if_invalid: SkipFieldsInvalid = None,
        expand_env_vars: ExpandEnvVarsMode | None = None,
        secret_field_names: Sequence[str] | None = None,
        masking_mode: MaskingMode | None = None,
        type_loaders: TypeLoaderMap | None = None,
        nested_resolve_strategy: NestedResolveStrategy | None = None,
        nested_resolve: NestedResolve | None = None,
    ) -> T: ...

    @overload
    def load(
        self,
        *sources: SourceProtocol,
        schema: None = None,
        cache: bool | timedelta | None = None,
        cache_engine: bool | None = None,
        stale_on_error: StaleOnErrorMode | None = None,
        debug: bool | None = None,
        strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
        field_merges: FieldMergeMap | None = None,
        field_groups: Sequence[FieldGroupTuple] = (),
        root_validators: Iterable[RootPredicate] = (),
        skip_if_broken: bool = False,
        skip_if_missing: bool = False,
        skip_field_if_invalid: SkipFieldsInvalid = None,
        expand_env_vars: ExpandEnvVarsMode | None = None,
        secret_field_names: Sequence[str] | None = None,
        masking_mode: MaskingMode | None = None,
        type_loaders: TypeLoaderMap | None = None,
        nested_resolve_strategy: NestedResolveStrategy | None = None,
        nested_resolve: NestedResolve | None = None,
    ) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]: ...

    def load(  # noqa: PLR0913
        self,
        *sources: SourceProtocol,
        schema: type[Any] | None = None,
        cache: bool | timedelta | None = None,
        cache_engine: bool | None = None,
        stale_on_error: StaleOnErrorMode | None = None,
        debug: bool | None = None,
        strategy: MergeStrategyName | SourceMergeStrategy = DEFAULT_STRATEGY,
        field_merges: FieldMergeMap | None = None,
        field_groups: Sequence[FieldGroupTuple] = (),
        root_validators: Iterable[RootPredicate] = (),
        skip_if_broken: bool = False,
        skip_if_missing: bool = False,
        skip_field_if_invalid: SkipFieldsInvalid = None,
        expand_env_vars: ExpandEnvVarsMode | None = None,
        secret_field_names: Sequence[str] | None = None,
        masking_mode: MaskingMode | None = None,
        type_loaders: TypeLoaderMap | None = None,
        nested_resolve_strategy: NestedResolveStrategy | None = None,
        nested_resolve: NestedResolve | None = None,
    ) -> Any:
        """Load config from *sources* into *schema*, or return a decorator if ``schema=None``.

        Behaves identically to ``dature.load(...)`` but uses this instance's config as the
        base, overridable per-call by any keyword argument.

        **Decorator mode note**: when used as ``@conf.load(source)`` (no ``schema``), the
        config is bound at *decoration time* (module import), not lazily per ``Settings()``
        call.  If you need the config determined at call time, use function mode:
        ``conf.load(source, schema=Settings)`` inside the function body.

        Type-loader priority: ``Dature`` < load-level < source.
        """
        kwargs: dict[str, Any] = {
            "cache": cache,
            "cache_engine": cache_engine,
            "stale_on_error": stale_on_error,
            "debug": debug,
            "strategy": strategy,
            "field_merges": field_merges,
            "field_groups": field_groups,
            "root_validators": root_validators,
            "skip_if_broken": skip_if_broken,
            "skip_if_missing": skip_if_missing,
            "skip_field_if_invalid": skip_field_if_invalid,
            "expand_env_vars": expand_env_vars,
            "secret_field_names": secret_field_names,
            "masking_mode": masking_mode,
            "type_loaders": self._merge_type_loaders(type_loaders),
            "nested_resolve_strategy": nested_resolve_strategy,
            "nested_resolve": nested_resolve,
            "config": self._config,
        }
        if schema is not None:
            return dispatch(*sources, schema=schema, **kwargs)
        return dispatch(*sources, **kwargs)

    def loader[T: DataclassInstance](  # noqa: PLR0913
        self,
        *sources: SourceProtocol,
        schema: type[T],
        cache: bool | timedelta | None = None,
        cache_engine: bool | None = None,
        stale_on_error: StaleOnErrorMode | None = None,
        debug: bool | None = None,
        strategy: MergeStrategyName | SourceMergeStrategy = "last_wins",
        field_merges: FieldMergeMap | None = None,
        field_groups: Sequence[FieldGroupTuple] = (),
        root_validators: Iterable[RootPredicate] = (),
        skip_if_broken: bool = False,
        skip_if_missing: bool = False,
        skip_field_if_invalid: SkipFieldsInvalid = None,
        expand_env_vars: ExpandEnvVarsMode | None = None,
        secret_field_names: Sequence[str] | None = None,
        masking_mode: MaskingMode | None = None,
        type_loaders: TypeLoaderMap | None = None,
        nested_resolve_strategy: NestedResolveStrategy | None = None,
        nested_resolve: NestedResolve | None = None,
    ) -> Loader[T]:
        """Build and return a ``Loader`` configured with this instance's settings.

        Use this when you need the caching ``Loader`` object directly — e.g.
        to keep a cached loader across repeated calls or to access
        ``loader.secret_paths``.

        Type-loader priority: ``Dature`` < load-level < source.
        """
        return Loader(
            *sources,
            schema=schema,
            cache=cache,
            cache_engine=cache_engine,
            stale_on_error=stale_on_error,
            debug=debug,
            strategy=strategy,
            field_merges=field_merges,
            field_groups=field_groups,
            root_validators=root_validators,
            skip_if_broken=skip_if_broken,
            skip_if_missing=skip_if_missing,
            skip_field_if_invalid=skip_field_if_invalid,
            expand_env_vars=expand_env_vars,
            secret_field_names=secret_field_names,
            masking_mode=masking_mode,
            type_loaders=self._merge_type_loaders(type_loaders),
            nested_resolve_strategy=nested_resolve_strategy,
            nested_resolve=nested_resolve,
            config=self._config,
        )

    def _merge_type_loaders(self, type_loaders: TypeLoaderMap | None) -> TypeLoaderMap | None:
        """Merge instance-level type_loaders with load-level ones. Priority: instance < load-level."""
        if not self._type_loaders and not type_loaders:
            return None
        return {**(self._type_loaders or {}), **(type_loaders or {})}

    def __repr__(self) -> str:
        base = default_config()
        patterns = self._config.masking.secret_field_names
        mask = self._config.masking.mask
        parts = [
            f"{group}={_masked_group_repr(value, patterns=patterns, mask=mask)}"
            for group in _CONFIG_GROUP_NAMES
            if (value := getattr(self._config, group)) != getattr(base, group)
        ]
        if self._type_loaders:
            parts.append(f"type_loaders={self._type_loaders!r}")
        return f"Dature({', '.join(parts)})"


def _masked_group_repr(group: Any, *, patterns: tuple[str, ...], mask: str) -> str:  # noqa: ANN401
    """``repr()`` a config group dataclass with secret-looking fields (``token``, ``password``,
    ``vault.secret_id``, ``ssm.aws_secret_access_key``, etc.) replaced by *mask*.

    ``Dature.__repr__`` only ever shows groups that were explicitly overridden by the caller —
    unlike loaded config values, these never go through the masking pipeline, so without this
    a credential passed as e.g. ``Dature(vault={"token": "..."})`` would leak straight into
    ``repr(instance)``, logs, and tracebacks.
    """
    field_reprs = (
        f"{f.name}={mask!r}" if matches_secret_name(f.name, patterns) else f"{f.name}={getattr(group, f.name)!r}"
        for f in fields(group)
    )
    return f"{type(group).__name__}({', '.join(field_reprs)})"
