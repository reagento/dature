# Validation

dature supports multiple validation approaches: `Annotated` type hints, root validators, metadata validators, custom validators, and standard `__post_init__`.

## Annotated Validators

Declare validators using `typing.Annotated`:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/validation/validation_annotated.py:example"
    ```

=== "validation_annotated_invalid.json5"

    ```json5
    --8<-- "docs/examples/basic/validation/sources/validation_annotated_invalid.json5"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/basic/validation/validation_annotated.stderr"
    ```

### Available predicates

| Expression | Passes when | Type constraint |
|------------|-------------|-----------------|
| `V >= N` / `V > N` / `V <= N` / `V < N` / `V == N` / `V != N` | comparison holds | any comparable |
| `V.len() >= N` (and `>`, `<=`, `<`, `==`, `!=`) | length comparison holds | `Sized` |
| `V.matches(pattern)` | `re.match(pattern, value)` succeeds | `str` |
| `V.in_([...])` | value is in the collection | any |
| `V.unique_items()` | all items are unique | `Collection` |
| `V.each(inner)` | `inner` passes for every item | `Iterable` |
| `V.check(func, error_message=...)` | `func(value)` returns `True` | any |

Compose predicates with `&` (AND), `|` (OR), `~` (NOT). Override the default error message with `.with_error_message("...")` on leaf predicates.

!!! warning
    Chained comparisons like `3 <= V.len() <= 10` are not supported — Python collapses them to a bool before dature sees them. Use `(V.len() >= 3) & (V.len() <= 10)`.

## Root Validators

Validate the entire object after loading:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/validation/validation_root.py:example"
    ```

=== "validation_root_invalid.yaml"

    ```yaml
    --8<-- "docs/examples/basic/validation/sources/validation_root_invalid.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/basic/validation/validation_root.stderr"
    ```

Root validators receive the fully constructed dataclass instance and return `True` if valid. Pass them via `root_validators=` on `load()`, `Loader`, or `configure()` — they run once on the final merged object, after all sources have been applied.

## Metadata Validators

Field validators can be specified in `Source` using the `validators` parameter. Useful when the same dataclass is loaded from different sources with different validation rules. These validators **complement** (not replace) any `Annotated` validators:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/validation/validation_metadata.py:example"
    ```

=== "validation_metadata_invalid.yaml"

    ```yaml
    --8<-- "docs/examples/basic/validation/sources/validation_metadata_invalid.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/basic/validation/validation_metadata.stderr"
    ```

A single validator can be passed directly. Multiple validators require a tuple:

```python
--8<-- "docs/examples/basic/validation/validation_metadata_syntax.py"
```

Nested fields are supported via `F[Config].field` — see [Field Paths](field-paths.md):

```python
--8<-- "docs/examples/basic/validation/validation_metadata_nested.py"
```

## Custom Validators

Create your own validators by implementing `get_validator_func()` and `get_error_message()`. The validator must be a frozen dataclass:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/validation/validation_custom.py:example"
    ```

=== "validation_custom_invalid.json5"

    ```json5
    --8<-- "docs/examples/basic/validation/sources/validation_custom_invalid.json5"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/basic/validation/validation_custom.stderr"
    ```

Custom validators can be combined with built-in ones in `Annotated`.

## Validators During Merging

### Skip-invalid probe

When `skip_invalid_fields=True`, dature silently drops any field whose value fails
**coercion or a field validator** (`Annotated` predicates and `source.validators`). Business-rule
violations cause the field to be omitted rather than an error being raised.

### Per-source validator semantics

Field validators (`Annotated` predicates and `source.validators`) fire **per-source**, only on fields that the source actually provided, on the coerced value:

- A field provided by multiple sources is validated once per source that provides it.
- A field that a source did not provide is **not** validated by that source's pass — no missing-field error is raised for absent fields.
- A field that comes solely from a dataclass default is validated once at the end on the final object.

Root validators (`root_validators=`) run **once** on the final merged object after all field validation passes have completed.


## `__post_init__` and `@property`

Standard dataclass `__post_init__` and `@property` work as expected — dature preserves them during loading:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/validation/validation_post_init.py:example"
    ```

=== "validation_post_init_invalid.yaml"

    ```yaml
    --8<-- "docs/examples/basic/validation/sources/validation_post_init_invalid.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/basic/validation/validation_post_init.stderr"
    ```

Both approaches work in function mode and decorator mode.

## Error Format

Validation errors include field path, source location, and the offending value. The format varies by source type:

=== "YAML"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_yaml.py:example"
    ```

    ```
    --8<-- "docs/examples/basic/validation/error_format_yaml.stderr"
    ```

=== "JSON"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_json.py:example"
    ```

    ```
    --8<-- "docs/examples/basic/validation/error_format_json.stderr"
    ```

=== "JSON5"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_json5.py:example"
    ```

    ```
    --8<-- "docs/examples/basic/validation/error_format_json5.stderr"
    ```

=== "TOML"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_toml.py:example"
    ```

    ```
    --8<-- "docs/examples/basic/validation/error_format_toml.stderr"
    ```

=== "INI"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_ini.py:example"
    ```

    ```
    --8<-- "docs/examples/basic/validation/error_format_ini.stderr"
    ```

=== "ENV"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_env.py"
    ```

    ```
    --8<-- "docs/examples/basic/validation/error_format_env.stderr"
    ```

=== "ENV file"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_env_file.py:example"
    ```

    ```
    --8<-- "docs/examples/basic/validation/error_format_env_file.stderr"
    ```

=== "Docker Secrets"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_docker.py:example"
    ```

    ```
    --8<-- "docs/examples/basic/validation/error_format_docker.stderr"
    ```

### Multi-line value

When a value spans multiple source lines, each visible line is shown under the `├──` prefix with a caret underlining it so the whole offending block is visible at a glance. Long values are truncated after a few lines:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_multiline.py:example"
    ```

=== "multiline.yaml"

    ```yaml
    --8<-- "docs/examples/basic/validation/sources/error_format_multiline.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/basic/validation/error_format_multiline.stderr"
    ```

### Dataclass value

A custom validator can be attached to a dataclass-typed field via `Annotated`. The error shows the whole nested block from the source:

=== "Python"

    ```python
    --8<-- "docs/examples/basic/validation/error_format_dataclass.py:example"
    ```

=== "dataclass.yaml"

    ```yaml
    --8<-- "docs/examples/basic/validation/sources/error_format_dataclass.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/basic/validation/error_format_dataclass.stderr"
    ```

All field errors are collected and reported together — dature doesn't stop at the first error.
