# Validation

dature supports multiple validation approaches: `Annotated` type hints, root validators, metadata validators, custom validators, and standard `__post_init__`.

## Annotated Validators

Declare validators using `typing.Annotated`:

=== "Python"

    ```python
    --8<-- "examples/docs/features/validation/validation_annotated.py"
    ```

=== "validation_annotated_invalid.json5"

    ```json5
    --8<-- "examples/docs/features/validation/sources/validation_annotated_invalid.json5"
    ```

=== "Error"

    ```
    --8<-- "examples/docs/features/validation/validation_annotated.stderr"
    ```

### Available Validators

**Numbers** (`dature.validators.number`):

| Validator | Description |
|-----------|-------------|
| `Gt(N)` | Greater than N |
| `Ge(N)` | Greater than or equal to N |
| `Lt(N)` | Less than N |
| `Le(N)` | Less than or equal to N |

**Strings** (`dature.validators.string`):

| Validator | Description |
|-----------|-------------|
| `MinLength(N)` | Minimum string length |
| `MaxLength(N)` | Maximum string length |
| `RegexPattern(r"...")` | Match regex pattern |

**Sequences** (`dature.validators.sequence`):

| Validator | Description |
|-----------|-------------|
| `MinItems(N)` | Minimum number of items |
| `MaxItems(N)` | Maximum number of items |
| `UniqueItems()` | All items must be unique |

Multiple validators can be combined:

```python
--8<-- "examples/docs/features/validation/validation_annotated_combined.py:combined"
```

## Root Validators

Validate the entire object after loading:

=== "Python"

    ```python
    --8<-- "examples/docs/features/validation/validation_root.py"
    ```

=== "validation_root_invalid.yaml"

    ```yaml
    --8<-- "examples/docs/features/validation/sources/validation_root_invalid.yaml"
    ```

=== "Error"

    ```
    --8<-- "examples/docs/features/validation/validation_root.stderr"
    ```

Root validators receive the fully constructed dataclass instance and return `True` if valid.

## Metadata Validators

Field validators can be specified in `Source` using the `validators` parameter. Useful when the same dataclass is loaded from different sources with different validation rules. These validators **complement** (not replace) any `Annotated` validators:

=== "Python"

    ```python
    --8<-- "examples/docs/features/validation/validation_metadata.py"
    ```

=== "validation_metadata_invalid.yaml"

    ```yaml
    --8<-- "examples/docs/features/validation/sources/validation_metadata_invalid.yaml"
    ```

=== "Error"

    ```
    --8<-- "examples/docs/features/validation/validation_metadata.stderr"
    ```

A single validator can be passed directly. Multiple validators require a tuple:

```python
--8<-- "examples/docs/features/validation/validation_metadata_syntax.py:syntax"
```

Nested fields are supported:

```python
--8<-- "examples/docs/features/validation/validation_metadata_nested.py:nested"
```

## Custom Validators

Create your own validators by implementing `get_validator_func()` and `get_error_message()`. The validator must be a frozen dataclass:

=== "Python"

    ```python
    --8<-- "examples/docs/features/validation/validation_custom.py"
    ```

=== "validation_custom_invalid.json5"

    ```json5
    --8<-- "examples/docs/features/validation/sources/validation_custom_invalid.json5"
    ```

=== "Error"

    ```
    --8<-- "examples/docs/features/validation/validation_custom.stderr"
    ```

Custom validators can be combined with built-in ones in `Annotated`.

## `__post_init__` and `@property`

Standard dataclass `__post_init__` and `@property` work as expected — dature preserves them during loading:

=== "Python"

    ```python
    --8<-- "examples/docs/features/validation/validation_post_init.py"
    ```

=== "validation_post_init_invalid.yaml"

    ```yaml
    --8<-- "examples/docs/features/validation/sources/validation_post_init_invalid.yaml"
    ```

=== "Error"

    ```
    --8<-- "examples/docs/features/validation/validation_post_init.stderr"
    ```

Both approaches work in function mode and decorator mode.

## Error Format

Validation errors include source location and context. The format varies by source type:

=== "YAML"

    ```
    Config loading errors (1)

      [port]  Value must be >= 1
       └── FILE 'config.yaml', line 1
           port: -1
    ```

=== "JSON"

    ```
    Config loading errors (1)

      [port]  Value must be >= 1
       └── FILE 'config.json', line 1
           {"port": -1}
    ```

=== "JSON5"

    ```
    Config loading errors (1)

      [port]  Value must be >= 1
       └── FILE 'config.json5', line 1
           {port: -1}
    ```

=== "TOML"

    ```
    Config loading errors (1)

      [port]  Value must be >= 1
       └── FILE 'config.toml', line 1
           port = -1
    ```

=== "ENV file"

    ```
    Config loading errors (1)

      [port]  Value must be >= 1
       └── ENV FILE '.env', line 1
           PORT=-1
    ```

=== "ENV"

    ```
    Config loading errors (1)

      [port]  Value must be >= 1
       └── ENV 'APP_PORT'
    ```

=== "INI"

    ```
    Config loading errors (1)

      [port]  Value must be >= 1
       └── FILE 'config.ini', line 2
           port = -1
    ```

=== "Docker Secrets"

    ```
    Config loading errors (1)

      [port]  Value must be >= 1
       └── SECRET FILE '/run/secrets/port'
    ```

All field errors are collected and reported together — dature doesn't stop at the first error.
