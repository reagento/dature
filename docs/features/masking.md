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
       password: <REDACTED>
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

    ```title="Error"
    --8<-- "examples/docs/features/masking/masking_secret_str.stderr"
    ```

=== "By name"

    Fields whose names contain known patterns are automatically masked in error messages:

    ```python
    --8<-- "examples/docs/features/masking/masking_by_name.py"
    ```

    ```yaml title="masking_by_name.yaml"
    --8<-- "examples/docs/features/masking/sources/masking_by_name.yaml"
    ```

    ```title="Error"
    --8<-- "examples/docs/features/masking/masking_by_name.stderr"
    ```

=== "Heuristic"

    With `dature[secure]`, values that look like random tokens are masked in error messages even if the field name is not a known secret pattern:

    ```python
    --8<-- "examples/docs/features/masking/masking_heuristic.py"
    ```

    ```yaml title="masking_heuristic.yaml"
    --8<-- "examples/docs/features/masking/sources/masking_heuristic.yaml"
    ```

    ```title="Error"
    --8<-- "examples/docs/features/masking/masking_heuristic.stderr"
    ```

## Mask Format

By default, the entire value is replaced with `<REDACTED>`:

- `"my_secret_password"` → `"<REDACTED>"`
- `"1234"` → `"<REDACTED>"`

Configure `visible_prefix` / `visible_suffix` to keep characters visible at the start/end:

If `visible_prefix + visible_suffix >= len(value)`, the value is shown as-is.

Classic `ab*****cd` style:

```python
--8<-- "examples/docs/features/masking/masking_classic_style.py:classic-style"
```

## Configuration

### Per-source

Control masking via `Source`:

=== "secret_field_names"

    ```python
    --8<-- "examples/docs/features/masking/masking_per_source.py"
    ```

    ```title="Error"
    --8<-- "examples/docs/features/masking/masking_per_source.stderr"
    ```

=== "mask_secrets=False"

    ```python
    --8<-- "examples/docs/features/masking/masking_no_mask.py"
    ```

    ```title="Error"
    --8<-- "examples/docs/features/masking/masking_no_mask.stderr"
    ```

### Per-load

`mask_secrets` and `secret_field_names` can be passed directly to `dature.load()`. They apply to both single-source and multi-source modes. `Source.mask_secrets` overrides `load(mask_secrets=...)` when not `None`. `Source.secret_field_names` and `load(secret_field_names=...)` are combined.

### In merge mode

```python
--8<-- "examples/docs/features/masking/masking_merge_mode.py"
```

```title="Error"
--8<-- "examples/docs/features/masking/masking_merge_mode.stderr"
```

### Global

See [Advanced — Configure](../advanced/configure.md#global-configure) for global masking defaults and all available config options.
