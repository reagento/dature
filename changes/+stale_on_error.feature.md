Add `stale_on_error: Literal["keep", "raise", "retry"]` to `Loader`/`dature.load()` (function-mode
only via `configure()`/`Loader`) and to `configure(loading={...})`/`DATURE_LOADING__STALE_ON_ERROR`,
controlling what happens when a cached config's TTL expires and the reload fails: `"keep"` returns
the previously loaded config and restarts the TTL window, `"retry"` returns it without restarting
the window so the next call retries the reload, and `"raise"` propagates the error as before.

**Breaking change:** the default is now `"keep"` — a reload failure after a live TTL cache used to
always raise; it now silently falls back to the last successfully loaded config (with a
`logging.WARNING`) unless `stale_on_error="raise"` is set explicitly or globally via `configure()`.
