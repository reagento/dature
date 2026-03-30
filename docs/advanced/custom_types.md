# Custom Types & Loaders

## Custom Types

Use `type_loaders` to teach dature how to parse custom types from strings.

Pass `type_loaders` as a `dict[type, Callable]` mapping types to conversion functions:

```python
--8<-- "examples/docs/advanced/custom_types/custom_type.py"
```

```yaml title="custom_type_common.yaml"
--8<-- "examples/docs/advanced/custom_types/sources/custom_type_common.yaml"
```

### Per-source vs Global

`type_loaders` can be set per-source in `Source`, in `dature.load()` for merge mode, or globally via `configure()`:

=== "Per-source (Source)"

    ```python
    --8<-- "examples/docs/advanced/custom_types/custom_type.py"
    ```

=== "Per-merge (load)"

    ```python
    --8<-- "examples/docs/advanced/custom_types/custom_type_merge.py"
    ```

=== "Global (configure)"

    ```python
    --8<-- "examples/docs/advanced/custom_types/advanced_configure_type_loaders.py"
    ```

When both per-source and global `type_loaders` are set, they merge — per-source loaders take priority.

## Custom Loaders

For formats that dature doesn't support out of the box, subclass `BaseLoader` and implement two things:

1. `display_name` — a class-level string shown in error messages
2. `_load(path)` — returns `JSONValue` (a nested dict) from the source

```python
--8<-- "examples/docs/advanced/custom_types/custom_loader.py"
```

```xml title="custom_loader.xml"
--8<-- "examples/docs/advanced/custom_types/sources/custom_loader.xml"
```

Pass your custom loader via the `loader` parameter in `Source`. All built-in features (type coercion, validation, prefix extraction, ENV expansion) work automatically.
