# Naming

Control how dataclass field names map to config keys.

## name_style

Automatically convert between naming conventions. Maps dataclass field names (snake_case) to the convention used in config files.

| Value | Example |
|-------|---------|
| `lower_snake` | `my_field` |
| `upper_snake` | `MY_FIELD` |
| `lower_camel` | `myField` |
| `upper_camel` | `MyField` |
| `lower_kebab` | `my-field` |
| `upper_kebab` | `MY-FIELD` |

=== "Python"

    ```python
    --8<-- "examples/docs/naming_name_style.py"
    ```

=== "naming_name_style.yaml"

    ```yaml
    --8<-- "examples/docs/sources/naming_name_style.yaml"
    ```

## field_mapping

Explicit field renaming using `F` objects. Takes priority over `name_style`:

=== "Python"

    ```python
    --8<-- "examples/docs/naming_field_mapping.py"
    ```

=== "naming_field_mapping.yaml"

    ```yaml
    --8<-- "examples/docs/sources/naming_field_mapping.yaml"
    ```

### Multiple Aliases

A field can have multiple aliases — the first matching key in the source wins:

```python
field_mapping={F[Config].name: ("fullName", "userName")}
```

### Nested Fields

Nested fields are supported via `F[Owner].field` syntax on inner dataclasses:

=== "Python"

    ```python
    --8<-- "examples/docs/naming_nested_fields.py"
    ```

=== "naming_nested_fields.yaml"

    ```yaml
    --8<-- "examples/docs/sources/naming_nested_fields.yaml"
    ```

### Decorator Mode

In decorator mode where the class is not yet defined, use a string:

```python
F["Config"].name  # autocomplete doesn't work here
```

## prefix

Filters keys for ENV, or extracts a nested object from files:

```python
--8<-- "examples/docs/naming_prefix.py"
```

For file-based sources, `prefix` navigates into nested objects using dot notation:

=== "Python"

    ```python
    --8<-- "examples/docs/naming_prefix_nested.py"
    ```

=== "naming_prefix_nested.yaml"

    ```yaml
    --8<-- "examples/docs/sources/naming_prefix_nested.yaml"
    ```

## split_symbols

Delimiter for building nested structures from flat ENV variables and Docker secrets file names. Default: `"__"`.

```python
--8<-- "examples/docs/naming_split_symbols.py"
```
