# AzureAppConfigSource

`AzureAppConfigSource` loads configuration from [Azure App
Configuration](https://learn.microsoft.com/en-us/azure/azure-app-configuration/overview)'s
key-value store. It is a concrete implementation of the abstract
[`RemoteSource`](custom.md) base class and ships with the `dature[azure-appconfig]` optional
extra.

## Quickstart

Install the extra (pulls
[azure-appconfiguration](https://learn.microsoft.com/en-us/python/api/overview/azure/app-configuration-readme)
and [azure-identity](https://learn.microsoft.com/en-us/python/api/overview/azure/identity-readme)):

```bash
pip install dature[azure-appconfig]
```

```python
--8<-- "docs/examples/advanced/remote/azure_app_config/quickstart.py"
```

`AzureAppConfigSource` does **not** strip `key_filter` from key names — `key_filter` is a
glob passed straight to the SDK, and stripping a prefix out of a glob match is undefined.
With keys `myapp:db_password = s3cret`, `myapp:port = 5432`, `myapp:name = myapp` and
`key_filter="myapp:*"`, the loaded dict is
`{"myapp": {"db_password": "s3cret", "port": "5432", "name": "myapp"}}` — nest into the
`myapp` subtree with the standard [`Source.prefix`](../../introduction.md#source-reference)
field, as shown above.

## AzureAppConfigSource fields

- `endpoint` — App Configuration store endpoint, e.g. `https://my-store.azconfig.io`. Mutually
  exclusive with `connection_string`; exactly one must be set.
- `connection_string` — connection string carrying its own auth (`Endpoint=...;Id=...;Secret=...`).
  Mutually exclusive with `endpoint`, `credential` and `tenant_id`/`client_id`/`client_secret`.
- `key_filter` — glob passed to the SDK, e.g. `"myapp:*"`; default `None` fetches every key.
- `label_filter` — label glob; default `None`.
- `tenant_id` / `client_id` / `client_secret` — service principal credentials; must be set
  together, else `ValueError`.
- `credential` — a pre-built `azure.core.credentials.TokenCredential` (e.g.
  `ManagedIdentityCredential`, `WorkloadIdentityCredential`, `AzureCliCredential`). Takes
  precedence over `tenant_id`/`client_id`/`client_secret` and the `DefaultAzureCredential`
  fallback.
- `client_options` — extra kwargs forwarded to the SDK client constructor (`api_version`,
  `transport`, `connection_verify`, ...). Useful for pinning an API version behind a corporate
  proxy, or targeting a test double.
- `request_options` — extra kwargs forwarded to the SDK's `list_configuration_settings` call
  (`fields`, `tags_filter`, `accept_datetime`, `enforce_https`, ...). Needed for HTTP-only test
  doubles like the App Configuration emulator, which requires `enforce_https=False` with a
  bearer credential.
- `separator` — key segment separator for nesting; default `":"`.
- `decode` — how to decode each setting: `"utf-8"` (default) or `"json"`.

## Supported types

With `decode="utf-8"` (the default) every value is a string and collections are JSON
literals — the same dialect as ENV, with `:` nesting instead of `__`. Settings whose
`content_type` is `application/json` are always JSON-decoded regardless of `decode`.
`decode="json"` behaves like [`VaultSource`](vault.md) (native JSON), reading a single setting
whose value is an entire JSON document. See [Supported Types](../../supported_types.md) for the
full matrix.

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via
`dature.configure(azure_app_config={...})` (or the matching `DATURE_AZURE_APP_CONFIG__*` env
vars):

```python
--8<-- "docs/examples/advanced/remote/azure_app_config/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_AZURE_APP_CONFIG__*` env.
`None` on the instance means "fall through to the next layer". See
[Configure](../../basic/configure.md) for the full picture.

!!! note "Key Vault references are not resolved"
    Azure App Configuration settings can reference secrets stored in Azure Key Vault
    (`application/vnd.microsoft.appconfig.keyvaultref+json`). `AzureAppConfigSource`
    intentionally does not resolve these — merge in an [`AzureKeyVaultSource`](azure_key_vault.md)
    alongside it and let dature's own multi-source merge fill in the values:
    `load(AzureAppConfigSource(...), AzureKeyVaultSource(...))`.

!!! note "Credentials fall back to DefaultAzureCredential"
    Leaving `credential` and `tenant_id`/`client_id`/`client_secret` unset does not mean
    "no auth" — `DefaultAzureCredential` still resolves credentials from environment
    variables, a managed identity, or the Azure CLI, exactly as it would for any other
    Azure SDK call.
