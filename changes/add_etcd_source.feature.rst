Added :class:`EtcdSource` — loads configuration from etcd v3's KV store via ``etcd3gw``.
Install via ``pip install dature[etcd]``; connection settings can be set globally with
``configure(etcd={...})`` or ``DATURE_ETCD__*`` environment variables.
Supports recursive prefix reads with automatic ``/``-based nesting, single-key JSON
documents as config roots, raw ``bytes`` decode mode, and ``user``/``password`` RBAC
authentication built on top of ``etcd3gw``'s ``Etcd3Client.post()``. With ``decode="utf-8"``
(the default), JSON-literal collection values (``[1,2,3]``, ``{"k":"v"}``) are parsed
automatically, giving full type-coercion coverage matching the other flat-key sources
(ENV, Docker Secrets, ConsulSource).
