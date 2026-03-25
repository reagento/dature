# Masking

dature automatically masks secret values in error messages, debug logs, and `LoadReport` to prevent accidental leakage of sensitive data.

## Why Masking Matters

Without masking, a validation error or debug log could expose:

```
Config loading errors (1)

  [password]  Expected str, got int
   └── FILE 'config.yaml', line 2
       password: my_super_secret_password
```

With masking enabled (default):

```
Config loading errors (1)

  [password]  Expected str, got int
   └── FILE 'config.yaml', line 2
       password: my*****rd
```

## Detection Methods

dature uses three methods to identify secrets:

| Method | Description | Always active |
|--------|-------------|---------------|
| **By type** | Fields typed as `SecretStr` or `PaymentCardNumber` | Yes |
| **By name** | Field name contains a known pattern (case-insensitive) | Yes |
| **Heuristic** | String values that look like random tokens | Requires `dature[secure]` |

### Default Name Patterns

`password`, `passwd`, `secret`, `token`, `api_key`, `apikey`, `api_secret`, `access_key`, `private_key`, `auth`, `credential`

## Examples

=== "By type (SecretStr, PaymentCardNumber)"

    `SecretStr` and `PaymentCardNumber` mask values in `str()`, `repr()`, and debug logs:

    ```python
    --8<-- "examples/docs/features/masking/masking_secret_str.py"
    ```

    ```yaml title="masking_secret_str.yaml"
    --8<-- "examples/docs/features/masking/sources/masking_secret_str.yaml"
    ```

=== "By name"

    Fields whose names contain known patterns are automatically masked in error messages:

    ```python
    --8<-- "examples/docs/features/masking/masking_by_name.py"
    ```

    ```yaml title="masking_by_name.yaml"
    --8<-- "examples/docs/features/masking/sources/masking_by_name.yaml"
    ```

=== "Heuristic"

    With `dature[secure]`, values that look like random tokens are masked in error messages even if the field name is not a known secret pattern:

    ```python
    --8<-- "examples/docs/features/masking/masking_heuristic.py"
    ```

    ```yaml title="masking_heuristic.yaml"
    --8<-- "examples/docs/features/masking/sources/masking_heuristic.yaml"
    ```

## Mask Format

- Strings of 5+ characters: first 2 and last 2 characters visible, middle replaced with 5 `*`
    - `"my_secret_password"` → `"my*****rd"`
- Strings shorter than 5 characters: replaced with 5 `*`
    - `"1234"` → `"*****"`

## Configuration

### Per-source

Control masking via `Source` and `Merge`:

```python
# Add custom secret patterns (added to defaults)
config = load(
    Source(
        file_="config.yaml",
        secret_field_names=("connection_string", "dsn"),
    ),
    Config,
)

# Disable masking entirely
config = load(
    Source(file_="config.yaml", mask_secrets=False),
    Config,
)
```

### In merge mode

```python
config = load(
    Merge(
        (
            Source(file_="defaults.yaml"),
            Source(file_="secrets.yaml", secret_field_names=("custom_key",)),  # added to Merge patterns
        ),
        mask_secrets=True,  # enabled by default
        secret_field_names=("my_pattern",),  # extra patterns for all sources
    ),
    Config,
)
```

`Source.mask_secrets` overrides `Merge.mask_secrets` when not `None`. `secret_field_names` from both are combined.

### Global

See [Advanced — Configure](../advanced/configure.md#global-configure) for global masking defaults and all available config options.
