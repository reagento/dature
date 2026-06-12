# Conditional Sources

Use `when=` to include a source only when a condition is met.
A source that doesn't match is skipped entirely — it never touches the filesystem,
the network, or the dependency graph.

## Quick start

Set `when=` to a condition built with the `When()` DSL.
`When("${TEMPLATE}") == "value"` is true when the template expands to that value.
`when=None` (the default) means always enabled.

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/dev.py:example"
    ```

=== "vault_dev.env"

    ```env
    --8<-- "docs/examples/advanced/conditional_sources/sources/vault_dev.env"
    ```

Templates support the same `${VAR}` and `${@tag.key}` expansion syntax as source
init-fields.

## Combining conditions

=== "in_()"

    Use `.in_()` to enable the source when the template expands to **any** of several
    values.  `APP_ENV=local` matches `("dev", "local")`, so the source is enabled.

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/tuple_values.py:example"
    ```

=== "not_in()"

    Use `.not_in()` to enable the source for every value **except** the listed ones.
    Here the file source loads in all environments except prod.

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/not_in.py:example"
    ```

=== "AND (&)"

    Use `&` to require **all** conditions to match simultaneously.
    The source is enabled only when both `APP_ENV=prod` and `REGION` is `eu` or `us`.

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/multiple_keys.py:example"
    ```

=== "OR (|)"

    Use `|` to enable the source when **any** of the conditions matches.
    `APP_ENV=staging` satisfies the second branch, so the source is enabled.

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/or_conditions.py:example"
    ```

=== "NOT (~)"

    Use `~` to invert a condition.
    Here the source loads in every environment **except** prod.

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/not_operator.py:example"
    ```

Conditions compose freely: `(When("${A}") == "x") & (~When("${B}").in_("y", "z"))`.

## Defaults for unset variables

Use `${VAR:-default}` when the variable may not be set.  Both `when=` conditions must
use the **same** default so they stay mutually exclusive:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/env_var_default.py:example"
    ```

=== "vault_dev.env"

    ```env
    --8<-- "docs/examples/advanced/conditional_sources/sources/vault_dev.env"
    ```

Both conditions use the same default `"dev"` when `APP_ENV` is unset — exactly one source
is enabled, no collision.

### Error: all sources filtered out

Without a `:-default`, an unset variable expands to `""`, which matches nothing.
For example, if `APP_ENV` is not set, `${APP_ENV}` expands to an empty string 
and matches neither `"prod"` nor (`"dev"`, `"local"`). 
If all sources are conditional and none matches, `dature` raises a`DatureError`
immediately at construction time.

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/errors_all_filtered.py:example"
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
    --8<-- "docs/examples/advanced/conditional_sources/prod.py:example"
    ```

=== "dev"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/dev.py:example"
    ```

=== "vault_dev.env"

    ```env
    --8<-- "docs/examples/advanced/conditional_sources/sources/vault_dev.env"
    ```

Because `when=` conditions are mutually exclusive, only one source is ever active
and both sources can safely share the same `tag="secrets"`.

## Toggle from another source

Use `${@tag.key}` as a `When()` template when the toggle value lives in a file
or another source rather than in an OS environment variable.
For example, if the toggle value lives in `config.json`, not in an OS environment variable,
`JsonSource` loads first, and its `"env"` key drives the `when=` condition of `EnvFileSource`.


=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/source_toggle.py:example"
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
default raises.  Use `:-` to provide a fallback.

For example, config.json contains {"env": "dev"}. The "secrets" source is disabled lazily
because its when= depends on ${@cfg.env}, and env != "prod".
Even when disabled, sources still occupy their tag slot in the dependency graph,
so ${@secrets.remote_config} remains a valid reference — it simply resolves to absent.
In this case, the :- default is used and falls back to the local config.json instead.

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/ref_fallback.py:example"
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
`prefix=` or `field_mapping=` to load different subsets of keys conditionally.
For example, `base.env` (e.g. `DB_HOST`, `PORT`) is always loaded,
while the vault token is sourced from the OS environment in `prod` and from a local file in `dev`.

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/conditional_sources/same_tag.py:example"
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

If conditions overlap, two sources with the same explicit `tag=` are both enabled,
and `dature` raises a `DatureError` at construction time.
For example, if `APP_ENV` is not set, both `when=` conditions may fire simultaneously
because they use different defaults, resulting in two active sources under the same 
explicit `tag="secrets"`. Unlike a tag collision caused by `${@tag.key}` references,
this is detected at construction time whenever `tag=` is explicitly set - no consumer source is required.
Fix: use a consistent default across all conditions (see the `"no APP_ENV"` example).

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

Fix: use the same `:-default` in both `when=` conditions so exactly one matches
when the variable is unset.

## Interaction with `skip_if_broken`

`when=` filtering runs **before** any I/O: a source that doesn't match its
`when=` condition is never opened, never loaded, and never considered broken.
`skip_if_broken=True` (or the `skip_broken_sources=True` load-level flag) only
applies to sources that *pass* the `when=` gate and then raise during loading
(e.g. file not found).  In other words, a source disabled by its `when=` condition
always takes priority over `skip_if_broken`.

## Syntax reference

| Condition | Section |
|---|---|
| `When("${APP_ENV}") == "prod"` | [Quick start](#quick-start) |
| `When("${APP_ENV}") != "prod"` | [Combining conditions](#combining-conditions) |
| `When("${APP_ENV}").in_("dev", "local")` | [Combining conditions](#combining-conditions) |
| `When("${APP_ENV}").not_in("prod", "staging")` | [Combining conditions](#combining-conditions) |
| `(When("${A}") == "x") & (When("${B}") == "y")` — AND | [Combining conditions](#combining-conditions) |
| `(When("${A}") == "x") \| (When("${B}") == "y")` — OR | [Combining conditions](#combining-conditions) |
| `~(When("${APP_ENV}") == "prod")` — NOT | [Combining conditions](#combining-conditions) |
| `When("${APP_ENV:-dev}") == "prod"` — default when unset | [Defaults for unset variables](#defaults-for-unset-variables) |
| `When("${@tag.key}") == "prod"` | [Toggle from another source](#toggle-from-another-source) |


