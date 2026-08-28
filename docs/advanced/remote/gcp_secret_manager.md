# GcpSecretManagerSource

`GcpSecretManagerSource` loads secrets from [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs). It is a concrete implementation of the abstract [`RemoteSource`](custom.md) base class and ships with the `dature[gcp]` optional extra.

## Quickstart

Install the extra (pulls [google-cloud-secret-manager](https://cloud.google.com/python/docs/reference/secretmanager/latest), which brings in `google-auth` transitively):

```bash
pip install dature[gcp]
```

```python
--8<-- "docs/examples/advanced/remote/gcp_secret_manager/quickstart.py"
```

By default (`name="*"`) `GcpSecretManagerSource` lists **every** secret in the project and fetches each one, nesting names on `separator`. With secrets `db--password = s3cret`, `port = 5432`, `name = myapp` and `separator="--"`, the loaded dict is `{"db": {"password": "s3cret"}, "port": "5432", "name": "myapp"}` — Secret Manager secret ids only allow `[0-9A-Za-z_-]`, so a single `-` doubles as a literal character and cannot also be the nesting separator; hence the two-dash default.

## GcpSecretManagerSource fields

- `project_id` — GCP project id (required).
- `name` — a single secret id holding the whole config document. `"*"` (default) lists every secret and nests them instead.
- `version` — secret version: `"latest"` (default) or an explicit version number.
- `name_prefix` — in list mode, only secrets whose id starts with this prefix are fetched (server-side filter, translated to `name:<prefix>`).
- `labels` — in list mode, only secrets carrying all of these labels are fetched (server-side filter, translated to `labels.<k>=<v>` per label, `AND`-joined).
- `credentials` — a pre-built `google.auth.credentials.Credentials` object.
- `credentials_file` — path to a service-account JSON key file. Mutually exclusive with `credentials`.
- `transport` — a pre-built transport (e.g. `SecretManagerServiceGrpcTransport`). Mutually exclusive with `credentials`/`credentials_file` — useful for targeting a test double.
- `client_options` — extra kwargs forwarded to `SecretManagerServiceClient` (`api_endpoint`, ...).
- `separator` — secret id segment separator for nesting; default `"--"`.
- `decode` — how to decode each secret: `"utf-8"` (default) or `"json"`.

## Supported types

With `decode="utf-8"` (the default) every value is a string and collections are JSON literals — the same dialect as ENV, with `--` nesting instead of `__`. `decode="json"` behaves like [`VaultSource`](vault.md) (native JSON) when combined with `name` set — reading a single secret whose value is an entire JSON document. See [Supported Types](../../supported_types.md) for the full matrix.

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via `dature.configure(gcp_secret_manager={...})` (or the matching `DATURE_GCP_SECRET_MANAGER__*` env vars):

```python
--8<-- "docs/examples/advanced/remote/gcp_secret_manager/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_GCP_SECRET_MANAGER__*` env. `None` on the instance means "fall through to the next layer". See [Configure](../../basic/configure.md) for the full picture.

!!! note "List mode has a server-side filter"
    Unlike `AzureKeyVaultSource`, Secret Manager supports server-side filtering — `name_prefix` and `labels` are translated into Secret Manager's `filter` query, so list mode (`name="*"`) only enumerates matching secrets instead of every secret in the project. Fetching each matched secret's value is still one round trip per secret (N+1).

!!! note "Credentials fall back to Application Default Credentials"
    Leaving `credentials` and `credentials_file` unset does not mean "no auth" — Application Default Credentials (ADC) still resolves credentials from the environment (`GOOGLE_APPLICATION_CREDENTIALS`), a metadata server, or `gcloud auth application-default login`, exactly as it would for any other Google Cloud client library.
