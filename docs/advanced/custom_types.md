# Custom Types

Use `type_loaders` to teach dature how to parse custom types from strings.

Pass `type_loaders` as a `dict[type, Callable]` mapping types to conversion functions:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/custom_types/custom_type.py:example"
    ```

=== "custom_type_common.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/custom_types/sources/custom_type_common.yaml"
    ```

### Per-source vs Global

`type_loaders` can be set per-source in `Source`, in `dature.load()` for merge mode, or globally via `configure()`:

=== "Per-source (Source)"

    ```python
    --8<-- "docs/examples/advanced/custom_types/custom_type.py:example"
    ```

=== "Per-merge (load)"

    ```python
    --8<-- "docs/examples/advanced/custom_types/custom_type_merge.py:example"
    ```

=== "Global (configure)"

    ```python
    --8<-- "docs/examples/advanced/custom_types/advanced_configure_type_loaders.py:example"
    ```

When both per-source and global `type_loaders` are set, they merge — per-source loaders take priority.

