# Remote Source

`RemoteSource` is the abstract base for sources that fetch configuration from
remote services — secret managers, key-value stores, HTTP APIs. The only
implementation shipped today is `VaultSource` (HashiCorp Vault); the contract
is small enough to plug in your own (AWS Secrets Manager, Azure Key Vault,
Consul KV, …) by overriding two methods. See
[Implementing a custom RemoteSource](#implementing-a-custom-remotesource).

## Quickstart with VaultSource

Install the extra (pulls [hvac](https://github.com/hvac/hvac)):

```bash
pip install dature[vault]              # runtime only
pip install dature[vault,type-stubs]   # runtime + mypy/pyright stubs for hvac
```

```python
--8<-- "docs/examples/features/remote_source/quickstart.py:setup"
--8<-- "docs/examples/features/remote_source/quickstart.py:example"
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
--8<-- "docs/examples/features/remote_source/configure.py:setup"
--8<-- "docs/examples/features/remote_source/configure.py:example"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_VAULT__*`
env. `None` on the instance means "fall through to the next layer". See
[Configure](configure.md) for the full picture.

## Combining with other sources

`RemoteSource` composes with file/env/CLI sources via `load()` like any other
source. A common pattern is JSON/YAML for non-sensitive defaults, Vault for
secrets, env or CLI for last-mile overrides — order in `load()` controls
precedence (default `last_wins`). See [Merging](merging.md).

## Implementing a custom RemoteSource

`RemoteSource` is abstract. To plug in a different backend, subclass it and
implement two methods:

- `remote_address() -> str` — human-readable identifier shown in error
  messages and debug reports (e.g. an ARN, a URL, a Consul path).
- `_fetch() -> JSONValue` — perform the actual fetch and return a dict
  (mapping field names to values). The base class handles caching, prefix
  stripping, env-var expansion, and error-location rendering for free.

```python
--8<-- "docs/examples/features/remote_source/custom_source.py:setup"
--8<-- "docs/examples/features/remote_source/custom_source.py:example"
```

### Optional hooks

- `validate()` — runs after credential merge; override to enforce invariants
  (e.g. "either `token` or `role_id+secret_id` is set", as `VaultSource` does).
- `__repr__()` — defaults to `f"{self.format_name} '{self.remote_address()}'"`.

The `config_group` ClassVar that ties `VaultSource` to
`dature.configure(vault=...)` is wired into `dature.config.DatureConfig` and
is **not extensible from outside the package**. For a custom subclass, expose
connection params via constructor arguments.

!!! warning "Custom subclasses are not part of dature's API surface"

    `InMemorySource` above is a teaching example
