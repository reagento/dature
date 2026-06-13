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
| [ArgparseSource](cli/argparse.md) | Load argparse CLI arguments as a config source |
| [Custom CLI Source](cli/custom.md) | Plug in click, typer, or your own CLI parser |
| [VaultSource](remote/vault.md) | Fetch secrets from HashiCorp Vault |
| [Custom Remote Source](remote/custom.md) | Implement your own remote backend (AWS, Azure, Consul …) |
| [Custom Types & Loaders](custom_types.md) | Add support for new Python types or config formats |
| [Cross-Source Refs](cross_source_refs.md) | Reference values from one source inside another |
| [Conditional Sources](conditional_sources.md) | Activate sources based on environment or other config values |

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
| [Debug & Reports](debug.md) | `LoadReport`, `FieldOrigin`, debug logging |
| [Caching](caching.md) | Cache loaded configs with TTL and bucket-aligned invalidation |
