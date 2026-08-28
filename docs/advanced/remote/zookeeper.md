# ZookeeperSource

`ZookeeperSource` loads configuration from an [Apache ZooKeeper](https://zookeeper.apache.org/) znode tree. It is a concrete implementation of the abstract [`RemoteSource`](custom.md) base class and ships with the `dature[zookeeper]` optional extra.

## Quickstart

Install the extra (pulls [kazoo](https://kazoo.readthedocs.io/)):

```bash
pip install dature[zookeeper]
```

```python
--8<-- "docs/examples/advanced/remote/zookeeper/quickstart.py"
```

By default `ZookeeperSource` reads recursively (`recursive=True`) and splits znode paths on `/`, nesting them into a dict hierarchy. With the znode tree `myapp/db_password = s3cret`, `myapp/port = 5432`, `myapp/name = myapp` and `path="myapp"` the loaded dict is `{"db_password": "s3cret", "port": "5432", "name": "myapp"}`, which maps directly to a flat dataclass.

## ZookeeperSource fields

- `path` — ZooKeeper znode (`recursive=False`) or subtree root (`recursive=True`) (required).
- `hosts` — the ensemble address(es), as a comma-separated string (`"zk1:2181,zk2:2181"`, optionally with a trailing `/chroot`) or a list (`["zk1:2181", "zk2:2181"]`); default `""` (falls through to `ZookeeperConfig.hosts`, then `"localhost:2181"`). `DATURE_ZOOKEEPER__HOSTS` only accepts the string form.
- `user` / `password` — digest auth credentials; both `None` by default. Must be set together — setting only one raises `ValueError`. Mutually exclusive with `sasl_options`.
- `sasl_options` — a SASL options dict (e.g. `{"mechanism": "GSSAPI", ...}`) passed straight to `KazooClient`. Requires `kazoo[sasl]` (pulls `pure-sasl`) in addition to the base `zookeeper` extra.
- `timeout` — ZooKeeper session timeout in seconds; default `None` (kazoo's own default, 10s).
- `connection_timeout` — how long to wait for the initial connection in seconds; default `None` (kazoo's own default, 15s).
- `recursive` — read the subtree recursively; default `True`.
- `decode` — how to decode each znode's raw bytes: `"utf-8"` (default), `"json"`, or `"raw"`.
- `separator` — path segment separator for nesting; default `"/"`. Set to `None` to disable nesting.

!!! note "Znodes with both data and children"
    A znode that has children is treated as a pure intermediate node — its own data, if any, is dropped, since the nesting can't represent both a value and a subtree under the same key.

## Supported types

With `decode="utf-8"` (the default) every value is a string and collections are JSON literals — the same dialect as ENV, with `/` nesting instead of `__`. `decode="json"` behaves like [`VaultSource`](vault.md) (native JSON). `decode="raw"` yields raw `bytes` and sits outside the type-coercion matrix. See [Supported Types](../../supported_types.md) for the full matrix.

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via `dature.configure(zookeeper={...})` (or the matching `DATURE_ZOOKEEPER__*` env vars):

```python
--8<-- "docs/examples/advanced/remote/zookeeper/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_ZOOKEEPER__*` env. `None`, `""` or `[]` on the instance means "fall through to the next layer". See [Configure](../../basic/configure.md) for the full picture.
