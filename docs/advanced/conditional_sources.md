# Conditional Sources

Use `when=` to include a source only when a condition is met.
A source that doesn't match is skipped entirely — it never touches the filesystem,
the network, or the dependency graph.

## Quick start

Set `when=` to a mapping of template-string keys to expected values.
The source is enabled if **every** key expands to the expected value.

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/dev.py"
    ```

=== "vault_dev.env"

    ```env
    --8<-- "docs/examples/advanced/conditional_sources/sources/vault_dev.env"
    ```

Keys support the same `${VAR}` and `${@tag.key}` expansion syntax as source
init-fields.  `when=None` or `when={}` (the default) means always enabled.

## Allowing multiple values

Pass a tuple to accept any of several values:

```python
--8<-- "docs/examples/advanced/conditional_sources/tuple_values.py"
```

`APP_ENV=local` matches `("dev", "local")`, so the source is enabled.

## Combining conditions (AND)

List multiple keys to require all of them to match simultaneously:

```python
--8<-- "docs/examples/advanced/conditional_sources/multiple_keys.py"
```

The source is enabled only when both `APP_ENV=prod` **and** `REGION` is `eu`
or `us`.  If either key doesn't match, the source is skipped.

## Defaults for unset variables

Use `${VAR:-default}` when the variable may not be set.  Both `when=` keys must
share the **same** default so the conditions stay mutually exclusive:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/env_var_default.py"
    ```

=== "vault_dev.env"

    ```env
    --8<-- "docs/examples/advanced/conditional_sources/sources/vault_dev.env"
    ```

Both keys expand to `"dev"` when `APP_ENV` is unset — exactly one source is
enabled, no collision.

### Error: all sources filtered out

Without a `:-default`, an unset variable expands to `""`, which matches nothing.
If every source is conditional and none matches, dature raises immediately:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/errors_all_filtered.py"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/conditional_sources/errors_all_filtered.stderr"
    ```

## Switching environments

The same pattern scales to prod.  In prod the token is injected into the process
environment by the deployment platform; in dev it comes from a local file.
The `dature.load()` call is identical in both environments:

=== "prod"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/prod.py"
    ```

=== "dev"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/dev.py"
    ```

=== "vault_dev.env"

    ```env
    --8<-- "docs/examples/advanced/conditional_sources/sources/vault_dev.env"
    ```

Because `when=` conditions are mutually exclusive, only one source is ever active
and both sources can safely share the same `tag="secrets"`.

## Toggle from another source

Use `${@tag.key}` as a `when=` key when the toggle value lives in a file or
another source rather than in an OS environment variable:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/source_toggle.py"
    ```

=== "config.json"

    ```json
    --8<-- "docs/examples/advanced/conditional_sources/sources/config.json"
    ```

`JsonSource` loads first; its `env` key drives the `when=` of `EnvFileSource`.
Unlike `${VAR}` (resolved when `load()` is called), `${@tag.key}` is resolved
after the referenced source loads.

### Referencing a disabled source

A source disabled by a `${@tag.key}`-based `when=` still occupies its tag slot
in the dependency graph.  Its data is empty, so a cross-ref to it without a
default raises.  Use `:-` to provide a fallback:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/ref_fallback.py"
    ```

=== "config.json"

    ```json
    --8<-- "docs/examples/advanced/conditional_sources/sources/config.json"
    ```

`secrets` is disabled (`cfg.env` is `"dev"`, not `"prod"`), so
`${@secrets.remote_config}` is absent — the `:-` default fires instead.

## Same tag, different conditions

`when=` enables or disables a **Source instance** as a whole.  Multiple sources
can share the same `tag=` as long as their conditions are mutually exclusive — at
most one is active at a time.  Use separate instances with different
`prefix=` or `field_mapping=` to load different subsets of keys conditionally:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/same_tag.py"
    ```

=== "base.env"

    ```ini
    --8<-- "docs/examples/advanced/conditional_sources/sources/base.env"
    ```

=== "vault_dev.env"

    ```ini
    --8<-- "docs/examples/advanced/conditional_sources/sources/vault_dev.env"
    ```

`base.env` is always loaded (no `when=`); only the secrets source switches.

### Error: tag collision

If conditions overlap, two sources with the same explicit `tag=` are both
enabled — dature raises `DatureError` at construction time:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/errors_tag_collision_explicit.py"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/conditional_sources/errors_tag_collision_explicit.stderr"
    ```

The same collision can appear with auto-tags (no explicit `tag=`): two sources
of the same type share the same auto-tag, and the collision is detected only
when a downstream source references that tag:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/errors_tag_collision.py"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/conditional_sources/errors_tag_collision.stderr"
    ```

Fix: use the same `:-default` in both `when=` keys so exactly one condition
matches when the variable is unset.

## Interaction with `skip_if_broken`

`when=` filtering runs **before** any I/O: a source that doesn't match its
`when=` condition is never opened, never loaded, and never considered broken.
`skip_if_broken=True` (or the `skip_broken_sources=True` load-level flag) only
applies to sources that *pass* the `when=` gate and then raise during loading
(e.g. file not found).  In other words, `when=False` always takes priority over
`skip_if_broken`.

## Syntax reference

| Key form | Section |
|---|---|
| `"${APP_ENV}": "prod"` | [Quick start](#quick-start) |
| `"${APP_ENV}": ("dev", "local")` | [Multiple values](#allowing-multiple-values) |
| `"${APP_ENV:-dev}": "prod"`, two keys with same default | [Defaults for unset variables](#defaults-for-unset-variables) |
| `"${A}": …, "${B}": …` — multiple keys | [Combining conditions](#combining-conditions-and) |
| `"${@tag.key}": "prod"` | [Toggle from another source](#toggle-from-another-source) |
