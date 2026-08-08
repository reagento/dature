# EtcdSource

`EtcdSource` loads configuration from [etcd](https://etcd.io/) v3's KV store. It is a
concrete implementation of the abstract [`RemoteSource`](custom.md) base class and ships
with the `dature[etcd]` optional extra.

## Quickstart

Install the extra (pulls [etcd3gw](https://opendev.org/openstack/etcd3gw)):

```bash
pip install dature[etcd]
```

```python
--8<-- "docs/examples/advanced/remote/etcd/quickstart.py"
```

By default `EtcdSource` reads recursively (`recursive=True`) and splits keys on `/`,
nesting them into a dict hierarchy. With the KV tree
`myapp/db_password = s3cret`, `myapp/port = 5432`, `myapp/name = myapp`
and `path="myapp"` the loaded dict is `{"db_password": "s3cret", "port": "5432", "name": "myapp"}`,
which maps directly to a flat dataclass.

## EtcdSource fields

- `path` — etcd key (`recursive=False`) or prefix (`recursive=True`) (required).
- `host` — etcd address; default `""` (falls through to `EtcdConfig.host`, then `"localhost"`).
- `port` — etcd client port; default `None` (falls through to `EtcdConfig.port`, then `2379`).
- `protocol` — `"http"` or `"https"`; default `None` (falls through to `EtcdConfig.protocol`, then `"http"`).
- `user` / `password` — RBAC credentials; both `None` by default. Must be set together —
  setting only one raises `ValueError`. Without them, `load()` raises `PermissionError`
  whenever the etcd cluster has auth enabled.
- `ca_cert` — CA bundle path for TLS verification; default `None`.
- `cert_cert` / `cert_key` — client certificate pair for mTLS; default `None`.
- `timeout` — request timeout in seconds; default `None` (etcd3gw's own default).
- `recursive` — read the prefix tree recursively; default `True`.
- `decode` — how to decode each value's raw bytes: `"utf-8"` (default), `"json"`, or `"raw"`.
- `separator` — path segment separator for nesting; default `"/"`. Set to `None` to disable nesting.

## Supported types

With `decode="utf-8"` (the default) every value is a string and collections are
JSON literals — the same dialect as ENV, with `/` nesting instead of `__`.
`decode="json"` behaves like [`VaultSource`](vault.md) (native JSON). `decode="raw"`
yields raw `bytes` and sits outside the type-coercion matrix. See
[Supported Types](../../supported_types.md) for the full matrix.

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via
`dature.configure(etcd={...})` (or the matching `DATURE_ETCD__*` env vars):

```python
--8<-- "docs/examples/advanced/remote/etcd/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_ETCD__*` env.
`None` or `""` on the instance means "fall through to the next layer". See
[Configure](../../basic/configure.md) for the full picture.

!!! note "Authentication is layered on top of etcd3gw"
    `etcd3gw` has no built-in support for etcd's user/password auth. `EtcdSource`
    implements it itself: when `user` is set, it calls `POST /v3/auth/authenticate`
    through the client's own `post()` helper and stores the returned token on
    `client.session.headers["Authorization"]` before issuing any other request.
    `ca_cert` and `cert_cert`/`cert_key` are passed straight to `Etcd3Client`, which
    applies them to its own session.

!!! note "api_path autodiscovery"
    `EtcdSource` leaves `Etcd3Client`'s `api_path` on autodiscovery, which costs one
    extra `GET /version` request per `load()` call.
