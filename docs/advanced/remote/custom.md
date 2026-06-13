# Custom Remote Source

`RemoteSource` is the abstract base for sources that fetch configuration from
remote services — secret managers, key-value stores, HTTP APIs. Subclass it to
plug in any backend: AWS Secrets Manager, Azure Key Vault, Consul KV, or your own.

For the built-in HashiCorp Vault integration, see [VaultSource](vault.md).

## Implementing a custom RemoteSource

Subclass `RemoteSource` and implement two methods:

- `remote_address() -> str` — human-readable identifier shown in error
  messages and debug reports (e.g. an ARN, a URL, a Consul path).
- `_fetch() -> JSONValue` — perform the actual fetch and return a dict
  (mapping field names to values). The base class handles caching, prefix
  stripping, env-var expansion, and error-location rendering for free.

```python
--8<-- "docs/examples/advanced/remote/custom/custom_source.py"
```

## Optional hooks

- `validate()` — runs after credential merge; override to enforce invariants
  (e.g. "either `token` or `role_id+secret_id` is set", as `VaultSource` does).
- `__repr__()` — defaults to `f"{self.format_name} '{self.remote_address()}'"`.

The `config_group` ClassVar that ties `VaultSource` to
`dature.configure(vault=...)` is wired into `dature.config.DatureConfig` and
is **not extensible from outside the package**. For a custom subclass, expose
connection params via constructor arguments.

!!! warning "Not part of dature's API surface"

    The `InMemorySource` above is a teaching example. It is not shipped, not
    tested by dature's CI, and not bound by dature's backward-compatibility
    guarantees. Treat it as a starting point for your own implementation.
