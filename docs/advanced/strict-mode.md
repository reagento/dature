---
description: >-
  Catch typo'd config keys with dature's strict mode: warn, error, or ignore keys that don't map to any dataclass field, set globally or per-source.
---

# Strict Mode

By default, dature ignores config keys that don't map to any field on your dataclass — a typo
like `databse_host` in a config file silently loads as if it were never there. `strict` catches
this: it compares every key a source actually contributed against the schema and reports
anything left over, after the load itself succeeds.

`strict` accepts three values:

- `"off"` (default) — unknown keys are ignored.
- `"warn"` — unknown keys are logged (`logging.getLogger("dature")`, level `WARNING`); the load
  still succeeds.
- `"error"` — unknown keys raise a `StrictModeError`.

It can be set at `load()` level, on a `Dature` instance (`Dature(loading={"strict": "error"})`),
via `DATURE_LOADING__STRICT`, or per-`Source` — see [Per-source Override](#per-source-override)
below.

The check runs once, during the load that actually reads the source — a cached reload
(`Loader(..., cache=True)`, or `@conf.load(...)` reused across calls) returns the cached result
without re-checking, so a `"warn"` source only logs the first time its data is actually read, not
on every cache hit.

## Reporting an Unknown Key

The error points at the key itself — not its value — with a caret, plus the file and line it
came from:

```python
--8<-- "docs/examples/advanced/strict_mode/strict_json.py:example"
```

Nested keys are reported with their full dotted path (`db.typo_field`), and a typo inside a
`list`/`dict`/`tuple` of dataclasses is reported with its index or key in the path
(`items.1.hostt`, `envs.staging.hostt`).

Every source format is supported the same way — swap `JsonSource` above for any other source and
nothing else changes. `Json5Source` behaves exactly like `JsonSource`.

=== "JSON"

    ```json
    --8<-- "docs/examples/advanced/strict_mode/sources/strict_json.json"
    ```

    ```
    --8<-- "docs/examples/advanced/strict_mode/strict_json.stderr"
    ```

=== "YAML"

    ```yaml
    --8<-- "docs/examples/advanced/strict_mode/sources/strict_yaml.yaml"
    ```

    ```
    --8<-- "docs/examples/advanced/strict_mode/strict_yaml.stderr"
    ```

=== "TOML"

    ```toml
    --8<-- "docs/examples/advanced/strict_mode/sources/strict_toml.toml"
    ```

    ```
    --8<-- "docs/examples/advanced/strict_mode/strict_toml.stderr"
    ```

=== "INI"

    ```ini
    --8<-- "docs/examples/advanced/strict_mode/sources/strict_ini.ini"
    ```

    ```
    --8<-- "docs/examples/advanced/strict_mode/strict_ini.stderr"
    ```

=== ".env"

    ```dotenv
    --8<-- "docs/examples/advanced/strict_mode/sources/strict_env_file.env"
    ```

    ```
    --8<-- "docs/examples/advanced/strict_mode/strict_env_file.stderr"
    ```

## `strict="warn"`

Instead of raising, `"warn"` logs each unknown key and lets the load continue:

```python
--8<-- "docs/examples/advanced/strict_mode/strict_warn.py:example"
```

```
--8<-- "docs/examples/advanced/strict_mode/strict_warn.stdout"
```

## `EnvSource` Without a Prefix

`EnvSource` reads from the whole process environment. Without a `prefix`, *every* environment
variable is a candidate key — in a real shell that's easily 30+ variables, none of which have
anything to do with your config. Strict mode treats them all as "unknown keys", which is rarely
what you want, so `EnvSource` logs a warning the first time `strict` is anything but `"off"` and
no `prefix` is set:

```python
--8<-- "docs/examples/advanced/strict_mode/strict_env.py:example"
```

```
--8<-- "docs/examples/advanced/strict_mode/strict_env.stderr"
```

The list of unknown keys is capped at `max_errors` (see [Truncating Output](#truncating-output)
below) — here set to `3` — with a final `... and N more unknown config keys (M total)` note for
the rest.

The fix is the one the warning suggests: give the source its own prefix, so only variables you
actually control are in play.

```python
--8<-- "docs/examples/advanced/strict_mode/strict_env_prefixed.py:example"
```

This loads silently — `APP_HOST`/`APP_PORT` map to `host`/`port`, and everything else in the
environment is out of scope for this source.

## Per-source Override

`strict` can also be set directly on a `Source`, overriding whatever `load()` or the `Dature`
instance would otherwise use for that source only:

```python
--8<-- "docs/examples/advanced/strict_mode/strict_per_source_override.py:example"
```

Here `JsonSource` raises on its own `strict="error"` even though `load()` never sets `strict`
(default `"off"`); `EnvSource` has no `strict` of its own, so it falls back to that `"off"`
default and its keys go unchecked.

This is useful when one source is authoritative (say, a checked-in JSON file, where a typo is
always a mistake) and another is looser by nature (environment variables an operator might set
for unrelated tooling).

## Truncating Output

Both `"warn"` and `"error"` cap how many unknown-key blocks they show, via
`error_display.max_errors` ([API Reference](../api-reference.md#errordisplayconfig)) — the same
knob other dature errors use for "how many blocks is too many", kept independent of
`max_visible_lines` (which instead limits how many lines of source content one block shows):

```python
dature.Dature(error_display={"max_errors": 3})
```

With more unknown keys than that, the shown blocks are followed by a note —
`... and N more unknown config keys (M total)` — giving the true total; the group's own header
(`Config unknown config keys (N)`) only counts what's actually shown, matching how every other
dature exception group reports its size.
