---
description: >-
  Attach a background reload trigger to a cached dature config — FixedIntervalTrigger or FileWatchTrigger — to pick up changes without restarting the process.
---

# Background Reloading

`reload=` attaches a background trigger that periodically reloads a config and swaps the
cached instance in place, without restarting the process.

Think of it as an **external invalidation signal** for the cache: `cache=True` (the default)
caches forever on its own — `reload=` is what makes that cache eventually pick up changes.

=== "FixedIntervalTrigger"

    Reload unconditionally on a fixed cadence — the right choice for sources with no concept
    of "changed since last time" (env vars, remote KV stores).

    ```python
    --8<-- "docs/examples/advanced/reloading/reloading_fixed_interval.py"
    ```

=== "FileWatchTrigger"

    Reload when a watched file changes on disk. Watch paths are auto-derived from every
    `FileSource` in use — pass `paths=[...]` explicitly to watch something else.

    ```python
    --8<-- "docs/examples/advanced/reloading/reloading_file_watch.py"
    ```

## Callbacks, not a handle

`reload=` only takes callbacks — `on_reload=` (new instance) and `on_error=` (reload failure).
There is no public reload handle to poll or await. If you need to stop the background trigger
explicitly, keep a reference to the `Loader` yourself:

```python
--8<-- "docs/examples/advanced/reloading/reloading_stop.py:example"
```

`start_reload()`/`stop_reload()` are both idempotent-in-effect (the underlying trigger's
`stop()` must itself be safe to call repeatedly, per its protocol contract) — the background
reload thread starts lazily after the first successful `load()`, not at construction time.

## `reload=` and function mode

`reload=` requires keeping a `Loader` instance around to have anything to reload into — in
function mode (`dature.load(src, schema=Cls)`), the `Loader` is discarded right after the one
`.load()` call, so there's nothing for the background thread to update. Passing `reload=` in
function mode raises `ValueError` immediately; construct a `Loader` explicitly instead (see
[Function-mode caching](caching.md#function-mode-caching-loader)).

## Interaction with `cache`

Reloading writes into the same cache slot that `cache=True`/`cache=False` control — see the
table below. `cache=timedelta(...)` combined with `reload=` raises `ValueError`: the trigger
is already the invalidation signal, so a TTL on top of it would only add a redundant,
*blocking* reload every time the TTL bucket boundary is crossed.

| `cache` | Effect with `reload=` |
|---|---|
| `True` (default) | Reload publishes into the cache; the next `.load()` picks it up on the lock-free fast path. This is the intended combination. |
| `timedelta(N)` | `ValueError` — mutually exclusive with `reload=`. Use `cache=True` and set the interval on the trigger instead. |
| `False` | Reload still runs and still fires `on_reload`/`on_error`, but nothing is published — every `.load()` does its own full synchronous load regardless. Logs a warning, since this is usually a configuration mistake (though a legitimate use is wanting only the `on_reload` notification, with no caching at all). |

## `on_error` and `stale_on_error`

A failed reload never replaces the currently loaded config — `stale_on_error` (see
[Caching](caching.md#stale_on_error-keeping-the-last-good-config)) decides what happens to the
*cached* value, and `on_error` is called with the exception regardless of that choice.
`on_reload` is never called for a failed reload.

## Execution model

- **One background thread for the whole process** (named `dature-reload`), shared by every
  `Loader` that uses `reload=` — not one thread per `Loader`. It starts lazily on the first
  registration and stops once nothing is registered anymore.
- **Callbacks run sequentially on that one thread.** A slow reload (or a slow `on_reload`/
  `on_error` callback) for one `Loader` delays every other `Loader`'s reload, and a source
  with no timeout can stall reloading for the entire process. Give any remote source used
  with `reload=` its own timeout.
- Custom sources used with `reload=` must be safe to call from a background thread — `Loader`
  clones sources shallowly (`dataclasses.replace`), so a source holding a mutable client
  (a Vault/Consul/etcd connection, for example) shares that client between the foreground and
  the reload thread.
- In multi-process deployments (e.g. several gunicorn/uvicorn workers), each process runs its
  own reload thread and reloads independently — for a short window after a change, different
  workers may be serving different config versions.
- `FileWatchTrigger` resolves which paths to watch once, at `start()` time. If a config file's
  location later resolves to a different directory (e.g. via `find_config()`), the trigger
  keeps watching the original one.
- A custom trigger can be written directly against `ReloadTriggerProtocol`
  (`dature.reloading.protocol`) without subclassing anything — same pattern as `SourceProtocol`
  for sources.
- Every `ReloadTrigger` (`FixedIntervalTrigger`, `FileWatchTrigger`) accepts `scheduler=` to
  register on a dedicated `Scheduler` instead of the process-wide default — the sanctioned way
  to give a slow or unreliable reload source its own thread, isolated from every other trigger.

## Without `watchdog`

`FileWatchTrigger` requires the optional `watchdog` package — there is no fallback. The first
`load()` raises `ImportError` if it isn't installed:

```
pip install 'dature[watch]'
```
