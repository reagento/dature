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
    --8<-- "docs/examples/basic/naming/naming_name_style.py:example"
    ```

=== "naming_name_style.yaml"

    ```yaml
    --8<-- "docs/examples/basic/naming/sources/naming_name_style.yaml"
    ```

## field_mapping

Explicit field renaming using `F` objects. Takes priority over `name_style`:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/naming/naming_field_mapping.py:example"
    ```

=== "naming_field_mapping.yaml"

    ```yaml
    --8<-- "docs/examples/basic/naming/sources/naming_field_mapping.yaml"
    ```

### Multiple Aliases

A field can have multiple aliases — the first matching key in the source wins:

```python
--8<-- "docs/examples/basic/naming/naming_field_mapping_aliases.py:example"
```

### Nested Fields

Nested fields are supported via `F[Owner].field` syntax on inner dataclasses:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/naming/naming_nested_fields.py:example"
    ```

=== "naming_nested_fields.yaml"

    ```yaml
    --8<-- "docs/examples/basic/naming/sources/naming_nested_fields.yaml"
    ```

### Decorator Mode

In decorator mode where the class is not yet defined, use a string:

```python
--8<-- "docs/examples/basic/naming/naming_field_mapping_decorator.py:example"
```

## prefix

Filters keys for ENV, or extracts a nested object from files:

    ```python
    --8<-- "docs/examples/basic/naming/naming_prefix.py"
    ```

For file-based sources, `prefix` navigates into nested objects using dot notation:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/naming/naming_prefix_nested.py:example"
    ```

=== "naming_prefix_nested.yaml"

    ```yaml
    --8<-- "docs/examples/basic/naming/sources/naming_prefix_nested.yaml"
    ```

## nested_sep

Delimiter for building nested structures from flat ENV variables and Docker secrets file names. Default: `"__"`.

    ```python
    --8<-- "docs/examples/basic/naming/naming_nested_sep.py"
    ```
