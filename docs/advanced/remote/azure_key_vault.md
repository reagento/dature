# AzureKeyVaultSource

`AzureKeyVaultSource` loads secrets from [Azure Key
Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/overview). It is a concrete
implementation of the abstract [`RemoteSource`](custom.md) base class and ships with the
`dature[azure-keyvault]` optional extra.

## Quickstart

Install the extra (pulls
[azure-keyvault-secrets](https://learn.microsoft.com/en-us/python/api/overview/azure/keyvault-secrets-readme)
and [azure-identity](https://learn.microsoft.com/en-us/python/api/overview/azure/identity-readme)):

```bash
pip install dature[azure-keyvault]
```

```python
--8<-- "docs/examples/advanced/remote/azure_key_vault/quickstart.py"
```

By default (`name="*"`) `AzureKeyVaultSource` lists **every** secret in the vault and fetches
each one, nesting names on `separator`. With secrets `db-password = s3cret`, `port = 5432`,
`name = myapp` and `separator="--"`, the loaded dict is
`{"db_password": "s3cret", "port": "5432", "name": "myapp"}` — Key Vault secret names only allow
`[0-9A-Za-z-]`, so `-` doubles as a literal character and cannot also be the nesting separator;
hence the two-dash default.

## AzureKeyVaultSource fields

- `vault_url` — vault URL, e.g. `https://my-vault.vault.azure.net` (required).
- `name` — a single secret name holding the whole config document. `"*"` (default) lists every
  secret and nests them instead.
- `version` — secret version; default `None` (latest).
- `tenant_id` / `client_id` / `client_secret` — service principal credentials; must be set
  together, else `ValueError`.
- `credential` — a pre-built `azure.core.credentials.TokenCredential` (e.g.
  `ManagedIdentityCredential`, `WorkloadIdentityCredential`, `AzureCliCredential`). Takes
  precedence over `tenant_id`/`client_id`/`client_secret` and the `DefaultAzureCredential`
  fallback.
- `client_options` — extra kwargs forwarded to `SecretClient` (`api_version`, `transport`,
  `verify_challenge_resource`, ...). Useful for pinning an API version behind a corporate proxy,
  or targeting a test double.
- `separator` — secret name segment separator for nesting; default `"--"`.
- `decode` — how to decode each secret: `"utf-8"` (default) or `"json"`.

## Supported types

With `decode="utf-8"` (the default) every value is a string and collections are JSON
literals — the same dialect as ENV, with `--` nesting instead of `__`. `decode="json"` behaves
like [`VaultSource`](vault.md) (native JSON) when combined with `name` set — reading a single
secret whose value is an entire JSON document. See [Supported Types](../../supported_types.md)
for the full matrix.

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via
`dature.configure(azure_key_vault={...})` (or the matching `DATURE_AZURE_KEY_VAULT__*` env
vars):

```python
--8<-- "docs/examples/advanced/remote/azure_key_vault/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_AZURE_KEY_VAULT__*` env.
`None` on the instance means "fall through to the next layer". See
[Configure](../../basic/configure.md) for the full picture.

!!! note "List mode has no server-side filter"
    Unlike `AwsSsmSource`'s path-scoped `get_parameters_by_path` or `VaultSource`'s
    mount-scoped reads, Key Vault has no server-side prefix filter for secrets — list mode
    (`name="*"`) enumerates **every** secret in the vault, then fetches each one individually
    (N+1 round trips). For a vault with many unrelated secrets, prefer `name=...` pointing at a
    single JSON document, or a dedicated vault per application.

!!! note "Key Vault references are not resolved elsewhere"
    `AzureKeyVaultSource` only reads Key Vault directly; it does not resolve
    Key Vault references embedded in Azure App Configuration settings. Merge it with an
    [`AzureAppConfigSource`](azure_app_config.md) instead:
    `load(AzureAppConfigSource(...), AzureKeyVaultSource(...))`.

!!! note "Credentials fall back to DefaultAzureCredential"
    Leaving `credential` and `tenant_id`/`client_id`/`client_secret` unset does not mean
    "no auth" — `DefaultAzureCredential` still resolves credentials from environment
    variables, a managed identity, or the Azure CLI, exactly as it would for any other
    Azure SDK call.
