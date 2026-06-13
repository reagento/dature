# VaultSource

`VaultSource` loads configuration from [HashiCorp Vault](https://www.vaultproject.io/)
KV secrets engines. It is the shipped implementation of the abstract
[`RemoteSource`](custom.md) base class.

## Quickstart

Install the extra (pulls [hvac](https://github.com/hvac/hvac)):

```bash
pip install dature[vault]              # runtime only
pip install dature[vault,type-stubs]   # runtime + mypy/pyright stubs for hvac
```

```python
--8<-- "docs/examples/advanced/remote/vault/quickstart.py"
```

## VaultSource fields

- `url` — Vault address.
- `path` — secret path inside the mount (required).
- `token` **or** `role_id` + `secret_id` — authentication (mutually exclusive).
- `mount_point` — secrets engine mount; default `"secret"`.
- `kv_version` — `1` or `2`; default `2`.
- `namespace` — Vault Enterprise namespace.
- `verify` — TLS verification (`True`, a CA bundle path, or `False`).

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via
`dature.configure(vault={...})` (or the matching `DATURE_VAULT__*` env vars):

```python
--8<-- "docs/examples/advanced/remote/vault/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_VAULT__*`
env. `None` on the instance means "fall through to the next layer". See
[Configure](../../basic/configure.md) for the full picture.

## Combining with other sources

`VaultSource` composes with file/env/CLI sources via `load()` like any other
source. A common pattern is JSON/YAML for non-sensitive defaults, Vault for
secrets, env or CLI for last-mile overrides — order in `load()` controls
precedence (default `last_wins`). See [Merging](../../basic/merging.md).
