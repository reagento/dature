Added :class:`ConsulSource` — loads configuration from HashiCorp Consul KV store.
Install via ``pip install dature[consul]``; connection settings can be set globally with
``configure(consul={...})`` or ``DATURE_CONSUL__*`` environment variables.
Supports recursive prefix reads with automatic ``/``-based nesting, single-key JSON
documents as config roots, and raw ``bytes`` decode mode. With ``decode="utf-8"``
(the default), JSON-literal collection values (``[1,2,3]``, ``{"k":"v"}``) are parsed
automatically, giving full type-coercion coverage matching the other flat-key sources
(ENV, Docker Secrets).
