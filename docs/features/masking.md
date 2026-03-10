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

=== "secrets.yaml"

    ```yaml
    --8<-- "examples/docs/sources/secrets.yaml"
    ```

=== "By type (SecretStr, PaymentCardNumber)"

    `SecretStr` masks the value in `str()` and `repr()`:

    ```python
    --8<-- "examples/docs/masking_secret_str.py"
    ```

=== "By name"

    Fields whose names contain known patterns are automatically masked in logs and error messages:

    ```python
    --8<-- "examples/docs/masking_by_name.py"
    ```

    Debug logs show masked data:

    ```
    [Config] Loaded data: {'host': 'api.example.com', 'password': 'my*****rd', 'api_key': 'sk*****56'}
    ```

=== "Heuristic"

    With `dature[secure]`, values that look like random tokens are masked even if the field name is neutral:

    ```python
    --8<-- "examples/docs/masking_heuristic.py"
    ```

    Debug logs show masked data:

    ```
    [Config] Loaded data: {'host': 'api.example.com', 'password': 'my*****rd', 'api_key': 'sk*****56', 'card_number': '41*****11', 'metadata': 'aK*****T6'}
    ```

## Mask Format

- Strings of 5+ characters: first 2 and last 2 characters visible, middle replaced with 5 `*`
    - `"my_secret_password"` → `"my*****rd"`
- Strings shorter than 5 characters: replaced with 5 `*`
    - `"1234"` → `"*****"`

## Configuration

### Per-source

Control masking via `LoadMetadata` and `MergeMetadata`:

```python
# Add custom secret patterns (added to defaults)
config = load(
    LoadMetadata(
        file_="config.yaml",
        secret_field_names=("connection_string", "dsn"),
    ),
    Config,
)

# Disable masking entirely
config = load(
    LoadMetadata(file_="config.yaml", mask_secrets=False),
    Config,
)
```

### In merge mode

```python
config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_="defaults.yaml"),
            LoadMetadata(file_="secrets.yaml", secret_field_names=("custom_key",)),  # added to MergeMetadata patterns
        ),
        mask_secrets=True,  # enabled by default
        secret_field_names=("my_pattern",),  # extra patterns for all sources
    ),
    Config,
)
```

`LoadMetadata.mask_secrets` overrides `MergeMetadata.mask_secrets` when not `None`. `secret_field_names` from both are combined.

### Global

See [Advanced — Configure](../advanced/configure.md#global-configure) for global masking defaults and all available config options.
