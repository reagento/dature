# ConsulSource

`ConsulSource` loads configuration from [HashiCorp Consul](https://www.consul.io/)
KV store. It is a concrete implementation of the abstract
[`RemoteSource`](custom.md) base class and ships with the `dature[consul]` optional extra.

## Quickstart

Install the extra (pulls [py-consul](https://github.com/criteo-forks/py-consul)):

```bash
pip install dature[consul]
```

```python
--8<-- "docs/examples/advanced/remote/consul/quickstart.py"
```

By default `ConsulSource` reads recursively (`recursive=True`) and splits keys on `/`,
nesting them into a dict hierarchy. With the KV tree
`myapp/db_password = s3cret`, `myapp/port = 5432`, `myapp/name = myapp`
and `path="myapp"` the loaded dict is `{"db_password": "s3cret", "port": "5432", "name": "myapp"}`,
which maps directly to a flat dataclass.

## ConsulSource fields

- `path` — KV key (`recursive=False`) or prefix (`recursive=True`) inside Consul's KV store (required).
- `host` — Consul address; default `""` (falls through to `ConsulConfig.host`, then `"localhost"`).
- `port` — Consul HTTP port; default `None` (falls through to `ConsulConfig.port`, then `8500`).
- `scheme` — `"http"` or `"https"`; default `None` (falls through to `ConsulConfig.scheme`, then `"http"`).
- `token` — ACL token; default `None`.
- `datacenter` — Consul datacenter; default `None` (uses the agent's datacenter).
- `verify` — TLS verification: `True`, a CA bundle path, or `False`; default `None`.
- `recursive` — read the prefix tree recursively; default `True`.
- `decode` — how to decode each value's raw bytes: `"utf-8"` (default), `"json"`, or `"raw"`.
- `separator` — path segment separator for nesting; default `"/"`. Set to `None` to disable nesting.

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via
`dature.configure(consul={...})` (or the matching `DATURE_CONSUL__*` env vars):

```python
--8<-- "docs/examples/advanced/remote/consul/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_CONSUL__*` env.
`None` or `""` on the instance means "fall through to the next layer". See
[Configure](../../basic/configure.md) for the full picture.

!!! note "py-consul and CONSUL_HTTP_ADDR"
    `py-consul` falls back to the `CONSUL_HTTP_ADDR` environment variable only when
    both `host` and `port` are `None` (i.e. not set at the `Consul()` constructor level).
    With `ConsulSource`, `host` and `port` always flow through from `ConsulConfig`
    defaults (`"localhost"`, `8500`) — so `CONSUL_HTTP_ADDR` is never consulted.
    Use `configure(consul={"host": ..., "port": ...})` or `DATURE_CONSUL__HOST` /
    `DATURE_CONSUL__PORT` instead.

## Combining with other sources

`ConsulSource` composes with file/env/CLI sources via `load()` like any other
source. A common pattern is JSON/YAML for non-sensitive defaults, Consul for
secrets, env or CLI for last-mile overrides — order in `load()` controls
precedence (default `last_wins`). See [Merging](../../basic/merging.md).
