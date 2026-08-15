# Caching

In decorator mode, caching is enabled by default:

=== "cache=True"

    Caching stays active, so repeated loads reuse the first result until the inputs change. Cache can be invalidated.

    ```python
    --8<-- "docs/examples/advanced/caching/advanced_caching_enabled.py"
    ```

=== "cache=False"

    With caching disabled, each load reads the source again each time and picks up the new env value immediately.

    ```python
    --8<-- "docs/examples/advanced/caching/advanced_caching_disabled.py"
    ```

=== "cache=timedelta(...)"

    A `timedelta` enables TTL-based caching. This example patches `time.monotonic()` to simulate the cache expiring.

    ```python
    --8<-- "docs/examples/advanced/caching/advanced_caching_ttl.py"
    ```

Caching can also be configured globally via `configure()`.

## TTL caching

`cache` accepts a `datetime.timedelta` in addition to `bool`:

- `cache=True` — cache forever
- `cache=False` — never cache
- `cache=timedelta(seconds=N)` — cache for up to `N` seconds, then reload on the next access
- `cache=timedelta(0)` — equivalent to "always miss" (reload on every access)

TTL is measured via `time.monotonic()`, so it is immune to system clock changes. A negative `timedelta` raises `ValueError`.

### Bucket-aligned invalidation

TTL is **bucket-aligned** (cron-style): the stored timestamp snaps down to the nearest `monotonic % period == 0` boundary. The practical effect is that **every class loaded inside the same TTL window invalidates at the same instant**, regardless of when each individual `load()` happened.

Example with `cache=timedelta(minutes=15)`:

| Moment | Action | Effect |
|--------|--------|--------|
| `T=0` | Class A is first loaded | both A and B will invalidate at `T=15` |
| `T=5` | Class B is first loaded | shares A's bucket → invalidates at `T=15` |
| `T=15` | TTL boundary crossed | A and B go stale together |
| `T=16` | Class A reloaded | both refresh into the next bucket, expiring at `T=30` |

The first load in a window has an effectively shortened TTL (up to one period less than the full duration). This is the standard cron-style trade-off and matches the intuitive "invalidate every N minutes" mental model.

## `stale_on_error`: keeping the last good config

When a TTL window expires (or `when=` routing changes), the next `.load()` reloads from sources.
If that reload fails — a `Vault`/`Consul` outage, a YAML file rewritten mid-deploy — `stale_on_error`
decides what happens to the config that was already loaded successfully:

| Mode | Behavior on reload failure |
|------|-----------------------------|
| `"keep"` (default) | Return the previous config and **restart the TTL window** — a persistently broken source is not retried again until the window expires |
| `"retry"` | Return the previous config but leave the TTL window as-is — the **next** call retries the reload immediately |
| `"raise"` | Propagate the error (dature's original behavior, before `stale_on_error` existed) |

=== "stale_on_error=\"keep\""

    Reload fails → the previous config is returned and the TTL window restarts, so the broken
    source is not retried until the new window expires too.

    ```python
    --8<-- "docs/examples/advanced/caching/advanced_caching_stale_on_error_keep.py"
    ```

=== "stale_on_error=\"retry\""

    Reload fails → the previous config is returned but the TTL window is left as-is, so the
    very next call retries the reload immediately.

    ```python
    --8<-- "docs/examples/advanced/caching/advanced_caching_stale_on_error_retry.py"
    ```

=== "stale_on_error=\"raise\""

    Reload fails → the error propagates, same as dature's behavior before `stale_on_error` existed.

    ```python
    --8<-- "docs/examples/advanced/caching/advanced_caching_stale_on_error_raise.py"
    ```

    ```title="Error"
    --8<-- "docs/examples/advanced/caching/advanced_caching_stale_on_error_raise.stderr"
    ```

Notes:

- There is nothing to fall back to on the **first** load — a failure there always raises,
  regardless of `stale_on_error`.
- `stale_on_error` has no effect with `cache=False` (there is never a cached value to fall back to).
- When `when=` routing changes (an env var flips which sources are enabled), the cache is cleared
  before the reload attempt — a failure in that case always raises, since the stale value belongs
  to a different set of sources.
- Falling back to a stale value logs a `logging.WARNING` via the `"dature"` logger.
- `stale_on_error=None` (the default) falls back to `configure(loading={"stale_on_error": ...})`,
  same as `cache`/`cache_engine`.

## Function-mode caching: `Loader`

`dature.load(src, schema=Cls)` is a **thin shortcut** that constructs a throwaway `Loader` and calls `.load()` once. Repeated `load(...)` calls **do not share a cache** — each call is a fresh load.

To cache across calls in function mode, construct a `Loader` explicitly and keep the instance around:

```python
--8<-- "docs/examples/advanced/caching/advanced_caching_function.py"
```

The `Loader` carries all the load-time parameters and the cache state. Identity of the `Loader` instance fully captures the call configuration — there is no implicit fingerprinting of `debug`/`type_loaders`/`strategy`/etc. Different parameters → different `Loader` instances → independent cache slots.

### Loader API

| Method | Effect |
|---|---|
| `Loader.load() -> T` | Return cached result if fresh, else reload and cache. |
| `Loader.invalidate()` | Drop the cached result so the next `.load()` reloads from sources. |

`Loader` supports the same constructor parameters as `dature.load(...)` for function mode.

## `cache_engine`: retaining the compiled engine

`cache` caches the *loaded result*. `cache_engine` is a separate knob that controls whether the
**compiled engine** dature builds internally to convert raw source data into your dataclass is
kept around for reuse, or discarded after every load.

- `cache_engine=False` (the default) — nothing about the compiled engine is retained; each load
  builds it fresh and lets it go. This keeps a decorated class's retained memory low.
- `cache_engine=True` — the compiled engine is kept alive for the `Loader`/class lifetime, so
  repeated loads skip recompiling it. This is what makes a hot, uncached reload fast.
- `cache_engine=None` (the default when passed explicitly) — falls back to
  `configure(loading={"cache_engine": ...})`, same as other loading options.

Because the default `cache=True` already caches the result forever, the compiled engine is only
ever needed once — retaining it brings no benefit, so `cache_engine` defaults to `False`. Turn it
on explicitly when you need `cache=False` (or a short TTL) *and* a fast reload, at the cost of
extra retained memory. See the [benchmarks](../comparison/benchmarks.md) for the concrete
speed/memory trade-off.

```python
loader = Loader(source, schema=Config, cache=False, cache_engine=True)
```

