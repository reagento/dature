# Supported Types

## Type Coercion

String values from ENV and file formats are automatically converted.

All supported types in one dataclass:

```python
--8<-- "examples/all_types_dataclass.py"
```

### Coercion by Source

Different formats store values differently. YAML, JSON and TOML parse some types natively, while ENV and INI treat everything as strings:

=== "YAML"

    ```yaml
    --8<-- "examples/sources/all_types_yaml12.yaml"
    ```

=== "JSON"

    ```json
    --8<-- "examples/sources/all_types.json"
    ```

=== "TOML"

    ```toml
    --8<-- "examples/sources/all_types_toml11.toml"
    ```

=== "INI"

    ```ini
    --8<-- "examples/sources/all_types.ini"
    ```

=== "ENV"

    ```bash
    --8<-- "examples/sources/all_types.env"
    ```

For custom types and file format loaders, see [Custom Types & Loaders](advanced/custom_types.md).
