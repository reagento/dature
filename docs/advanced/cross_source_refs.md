# Cross-Source References

Sources can reference values from other sources using the `${@tag.key}` syntax.
This lets you pass a Vault token from an env variable, resolve a config file path
from a CLI argument, or build connection strings that combine several sources —
without imperative glue code.

## Quick start

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/cross_source_refs/quickstart.py:example"
    ```

=== "app.json"

    ```json
    --8<-- "docs/examples/advanced/cross_source_refs/sources/app.json"
    ```

The `env` in `${@env.config_path}` is the source **tag**.  By default the tag
equals the source type's `format_name` — `"env"` for `EnvSource`, `"json"` for
`JsonSource`, and so on.  Set `tag=` explicitly when you have two sources of the
same type.

Sources can be passed in any order: dature builds a dependency graph from
`${@tag.key}` patterns and loads them in topological order automatically.  In
the example above `JsonSource` is listed first but loaded second because it
depends on `EnvSource`.

## Syntax

| Pattern | Result |
|---|---|
| `${@tag.key}` | Value of `key` in the source tagged `tag` |
| `${@tag.section.key}` | Nested key path (dot-separated) |
| `${@tag.key:-default}` | Use `default` if `key` is absent |
| `$${@tag.key}` | Literal `${@tag.key}` (escape with `$$`) |

## Scope

`${@tag.key}` is only interpolated in a source's own constructor arguments
(e.g. `JsonSource(path=...)`, `VaultConfig(token=...)`) and in `when=`
conditions. It is **not** interpolated inside the data your config files
or environment carry — a `${@tag.key}` written in a YAML/JSON/TOML value
is passed through to the schema field literally, unchanged.

This is intentional: cross-refs describe how dature should locate or
connect to a source, not how that source's own data should be
transformed. Making config files use dature-specific syntax would couple
them to the tool. If you need a value from another source to end up in
the final config, merge that source in directly — for example
`DockerSecretsSource(dir_="/run/secrets")` merges its keys straight into
the schema, so no `${...}` is needed in any config file at all. For
pulling from an arbitrary external system, write a
[custom `Source`](custom_sources.md).

## Escaping

Prefix `$$` to produce a literal `$`. This is useful in a source's own
constructor argument, where `${@...}` would otherwise be treated as a
cross-ref — for example when a config-file *path* should contain `${@...}`
literally:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/cross_source_refs/escaping.py:example"
    ```

=== "${@env.something}"

    ```json
    --8<-- "docs/examples/advanced/cross_source_refs/sources/${@env.something}"
    ```

Escaping `$` in *data values* (as opposed to source arguments) is a
consequence of [env-var expansion](env-expansion.md), a separate feature —
see its [note on cross-refs](env-expansion.md#escaping-and-cross-source-refs).

## T-string syntax (Python 3.14+)

!!! info "Requires Python 3.14+"
    T-strings (PEP 750) are a Python 3.14 language feature.  On earlier versions
    use the `${@tag.key}` string syntax instead.

`from dature import ref` gives you a proxy object.  `ref.tag.key` inside a
t-string is exactly equivalent to `"${@tag.key}"` as a plain string:

=== "Python 3.14+"

    ```python
    --8<-- "docs/examples/advanced/cross_source_refs/t_string.py:example"
    ```

=== "app.json"

    ```json
    --8<-- "docs/examples/advanced/cross_source_refs/sources/app.json"
    ```

The format spec becomes the default value — `t"{ref.env.log_level:INFO}"` is
the same as `"${@env.log_level:-INFO}"`.

## Error messages

### Unknown tag

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/cross_source_refs/errors_unknown_tag.py"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/cross_source_refs/errors_unknown_tag.stderr"
    ```

### Cycle

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/cross_source_refs/errors_cycle.py"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/cross_source_refs/errors_cycle.stderr"
    ```

### Tag collision

Each source resolves to a tag that uniquely identifies it within a dature.load() call.
If two sources resolve to the same tag, dature raises an error.
EnvSource defaults to tag='env'. Loading two EnvSource instances without
explicitly setting a tag on at least one of them will cause a collision:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/cross_source_refs/errors_tag_collision.py"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/cross_source_refs/errors_tag_collision.stderr"
    ```


