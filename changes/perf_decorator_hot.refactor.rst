Decorator mode hot path is faster across the board:

- ``_prepare_for_load()`` (schema introspection + cross-ref plan) is cached and rebuilt only
  when the active source set changes (``when=`` flip), instead of on every cache miss.
- The base ``Retort(strict_coercion=True)`` is a module-level singleton, reducing decorator
  startup cost from ~190–210 µs to ~64–120 µs.
- The ``when=`` enabled-set computation (a per-source loop) is now skipped entirely when no
  source has a ``when=`` condition — the common case. The result is fixed at construction time.
- ``Config()`` calls without explicit field overrides now skip ``merge_fields`` and the
  revalidation pass (``asdict`` + validator re-run), since ``loaded_data`` exiting the load
  pipeline is already validated. This cuts ENV hot-path time from ~76 µs to ~64 µs, and
  cached-hit cost from ~10 µs to ~1.3 µs.
