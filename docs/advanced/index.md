---
description: >-
  Power-user dature features: merge strategies, remote sources like Vault and AWS SSM, custom types and sources, strict mode, caching and background reloading.
---

# Advanced

Power-user features for complex configuration setups. Most apps won't need all of these; pick what applies.

## Merging & Strategies

Fine-tune how multiple sources are combined.

| Page | What you'll learn |
|------|-------------------|
| [Merge Strategies](merge-strategies.md) | Per-field merge strategies; custom source-level strategy |
| [Field Groups](field-groups.md) | Enforce that related fields are always changed together |
| [Nested Resolve](nested-resolve.md) | Resolve conflicts between flat keys and JSON values in ENV sources |
| [Skip Behaviors](skip-behaviors.md) | Skip broken, missing, or invalid sources and fields |

## Sources

Integrate additional config sources or build your own.

| Page | What you'll learn |
|------|-------------------|
| [Config Search](config-search.md) | Automatic config file discovery |
| [Custom Types](custom_types.md) | Add support for new Python types via `type_loaders` |
| [Custom Sources](custom_sources.md) | Implement your own source class or use the `SourceProtocol` interface directly |
| [Cross-Source Refs](cross_source_refs.md) | Reference values from one source inside another |
| [Conditional Sources](conditional_sources.md) | Activate sources based on environment or other config values |
| [ArgparseSource](cli/argparse.md) | Load argparse CLI arguments as a config source |
| [Custom CLI Source](cli/custom.md) | Plug in click, typer, or your own CLI parser |
| [VaultSource](remote/vault.md) | Fetch secrets from HashiCorp Vault |
| [ConsulSource](remote/consul.md) | Fetch configuration from Consul |
| [EtcdSource](remote/etcd.md) | Fetch configuration from etcd |
| [ZookeeperSource](remote/zookeeper.md) | Fetch configuration from ZooKeeper |
| [AwsSsmSource](remote/ssm.md) | Fetch configuration from AWS Systems Manager Parameter Store |
| [AwsSecretsManagerSource](remote/secrets_manager.md) | Fetch secrets from AWS Secrets Manager |
| [AzureAppConfigSource](remote/azure_app_config.md) | Fetch configuration from Azure App Configuration |
| [AzureKeyVaultSource](remote/azure_key_vault.md) | Fetch secrets from Azure Key Vault |
| [GcpSecretManagerSource](remote/gcp_secret_manager.md) | Fetch secrets from Google Cloud Secret Manager |
| [Custom Remote Source](remote/custom.md) | Implement your own remote backend (AWS, Azure, Consul …) |

## Values

Control how field values are expanded and interpreted.

| Page | What you'll learn |
|------|-------------------|
| [ENV Expansion](env-expansion.md) | Expand `${VAR}` references inside config values |
| [Special Types](special-types.md) | `SecretStr`, `ByteSize`, `PaymentCardNumber`, `URL`, `Base64Url*` |

## Observability

Understand what dature loaded and where it came from.

| Page | What you'll learn |
|------|-------------------|
| [Strict Mode](strict-mode.md) | Warn, error, or ignore config keys that don't map to any dataclass field |
| [Debug & Reports](debug.md) | `LoadReport`, `FieldOrigin`, debug logging |
| [Caching](caching.md) | Cache loaded configs with TTL and bucket-aligned invalidation |
| [Reloading](reloading.md) | Background reload triggers (`FixedIntervalTrigger`, `FileWatchTrigger`) for cached configs |
