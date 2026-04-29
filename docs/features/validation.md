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

Validation errors include field path, source location, and the offending value. The format varies by source type:

=== "YAML"

    ```python
    --8<-- "examples/docs/features/validation/error_format_yaml.py"
    ```

    ```
    --8<-- "examples/docs/features/validation/error_format_yaml.stderr"
    ```

=== "JSON"

    ```python
    --8<-- "examples/docs/features/validation/error_format_json.py"
    ```

    ```
    --8<-- "examples/docs/features/validation/error_format_json.stderr"
    ```

=== "JSON5"

    ```python
    --8<-- "examples/docs/features/validation/error_format_json5.py"
    ```

    ```
    --8<-- "examples/docs/features/validation/error_format_json5.stderr"
    ```

=== "TOML"

    ```python
    --8<-- "examples/docs/features/validation/error_format_toml.py"
    ```

    ```
    --8<-- "examples/docs/features/validation/error_format_toml.stderr"
    ```

=== "INI"

    ```python
    --8<-- "examples/docs/features/validation/error_format_ini.py"
    ```

    ```
    --8<-- "examples/docs/features/validation/error_format_ini.stderr"
    ```

=== "ENV"

    ```python
    --8<-- "examples/docs/features/validation/error_format_env.py"
    ```

    ```
    --8<-- "examples/docs/features/validation/error_format_env.stderr"
    ```

=== "ENV file"

    ```python
    --8<-- "examples/docs/features/validation/error_format_env_file.py"
    ```

    ```
    --8<-- "examples/docs/features/validation/error_format_env_file.stderr"
    ```

=== "Docker Secrets"

    ```python
    --8<-- "examples/docs/features/validation/error_format_docker.py"
    ```

    ```
    --8<-- "examples/docs/features/validation/error_format_docker.stderr"
    ```

### Multi-line value

When a value spans multiple source lines, each visible line is shown under the `├──` prefix with a caret underlining it so the whole offending block is visible at a glance. Long values are truncated after a few lines:

=== "Python"

    ```python
    --8<-- "examples/docs/features/validation/error_format_multiline.py"
    ```

=== "multiline.yaml"

    ```yaml
    --8<-- "examples/docs/features/validation/sources/error_format_multiline.yaml"
    ```

=== "Error"

    ```
    --8<-- "examples/docs/features/validation/error_format_multiline.stderr"
    ```

### Dataclass value

A custom validator can be attached to a dataclass-typed field via `Annotated`. The error shows the whole nested block from the source:

=== "Python"

    ```python
    --8<-- "examples/docs/features/validation/error_format_dataclass.py"
    ```

=== "dataclass.yaml"

    ```yaml
    --8<-- "examples/docs/features/validation/sources/error_format_dataclass.yaml"
    ```

=== "Error"

    ```
    --8<-- "examples/docs/features/validation/error_format_dataclass.stderr"
    ```

All field errors are collected and reported together — dature doesn't stop at the first error.
