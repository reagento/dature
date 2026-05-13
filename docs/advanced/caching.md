# Caching

In decorator mode, caching is enabled by default:

=== "cache=True"

    ```python
    --8<-- "examples/docs/advanced/caching/advanced_caching_enabled.py"
    ```

=== "cache=False"

    ```python
    --8<-- "examples/docs/advanced/caching/advanced_caching_disabled.py"
    ```

=== "cache=timedelta(...)"

    ```python
    --8<-- "examples/docs/advanced/caching/advanced_caching_ttl.py"
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

## Function mode

`cache` works in function mode (`load(..., schema=Cls)`) too. The cache slot is attached to the `schema` class (under `__dature_cache__`), keyed by the participating sources. Decorator and function modes share the same storage — loading the same schema with the same source set via either mode hits the same cache slot. The slot dies with the schema class; no module-level state.

```python
--8<-- "examples/docs/advanced/caching/advanced_caching_function.py"
```
