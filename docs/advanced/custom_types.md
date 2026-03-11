# Custom Types & Loaders

## Custom Types

Use `type_loaders` to teach dature how to parse custom types from strings.

Each `TypeLoader` maps a type to a conversion function:

```python
--8<-- "examples/docs/custom_type.py"
```

```yaml title="custom_type_common.yaml"
--8<-- "examples/docs/sources/custom_type_common.yaml"
```

### Per-source vs Global

`type_loaders` can be set per-source in `LoadMetadata`, per-merge in `MergeMetadata`, or globally via `configure()`:

=== "Per-source (LoadMetadata)"

    ```python
    --8<-- "examples/docs/custom_type.py"
    ```

=== "Per-merge (MergeMetadata)"

    ```python
    --8<-- "examples/docs/custom_type_merge.py"
    ```

=== "Global (configure)"

    ```python
    --8<-- "examples/docs/advanced_configure_type_loaders.py"
    ```

When both per-source and global `type_loaders` are set, they merge — per-source loaders take priority (placed first in the recipe).

### TypeLoader Reference

```python
--8<-- "src/dature/metadata.py:type-loader"
```

| Parameter | Description |
|-----------|-------------|
| `type_` | The target type to register a loader for |
| `func` | A callable that converts the raw value to the target type |

## Custom Loaders

For formats that dature doesn't support out of the box, subclass `BaseLoader` and implement two things:

1. `display_name` — a class-level string shown in error messages
2. `_load(path)` — returns `JSONValue` (a nested dict) from the source

```python
--8<-- "examples/docs/custom_loader.py"
```

```xml title="custom_loader.xml"
--8<-- "examples/docs/sources/custom_loader.xml"
```

Pass your custom loader via the `loader` parameter in `LoadMetadata`. All built-in features (type coercion, validation, prefix extraction, ENV expansion) work automatically.
