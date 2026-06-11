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
    --8<-- "docs/examples/features/masking/masking_secret_str.py:setup"
    --8<-- "docs/examples/features/masking/masking_secret_str.py:example"
    ```

    ```yaml title="masking_secret_str.yaml"
    --8<-- "docs/examples/features/masking/sources/masking_secret_str.yaml"
    ```

    ```title="Error"
    --8<-- "docs/examples/features/masking/masking_secret_str.stderr"
    ```

=== "By name"

    Fields whose names contain known patterns are automatically masked in error messages:

    ```python
    --8<-- "docs/examples/features/masking/masking_by_name.py:setup"
    --8<-- "docs/examples/features/masking/masking_by_name.py:example"
    ```

    ```yaml title="masking_by_name.yaml"
    --8<-- "docs/examples/features/masking/sources/masking_by_name.yaml"
    ```

    ```title="Error"
    --8<-- "docs/examples/features/masking/masking_by_name.stderr"
    ```

=== "Heuristic"

    With `dature[secure]`, values that look like random tokens are masked in error messages even if the field name is not a known secret pattern:

    ```python
    --8<-- "docs/examples/features/masking/masking_heuristic.py:setup"
    --8<-- "docs/examples/features/masking/masking_heuristic.py:example"
    ```

    ```yaml title="masking_heuristic.yaml"
    --8<-- "docs/examples/features/masking/sources/masking_heuristic.yaml"
    ```

    ```title="Error"
    --8<-- "docs/examples/features/masking/masking_heuristic.stderr"
    ```

## Mask Format

By default, the entire value is replaced with `<REDACTED>`:

- `"my_secret_password"` → `"<REDACTED>"`
- `"1234"` → `"<REDACTED>"`

Configure `visible_prefix` / `visible_suffix` to keep characters visible at the start/end:

If `visible_prefix + visible_suffix >= len(value)`, the value is shown as-is.

Classic `ab*****cd` style:

```python
--8<-- "docs/examples/features/masking/masking_classic_style.py:example"
```
* `"my_secret_password"` → `"my*****rd"`
* `"ab"` → `"ab"` (too short — shown as-is)

## Configuration

### Per-load

`mask_secrets` and `secret_field_names` are passed directly to `dature.load()`. They apply to both single-source and multi-source modes.

=== "mask_secrets=False"

    ```python
    --8<-- "docs/examples/features/masking/masking_no_mask.py:setup"
    --8<-- "docs/examples/features/masking/masking_no_mask.py:example"
    ```

    ```title="Error"
    --8<-- "docs/examples/features/masking/masking_no_mask.stderr"
    ```

### In merge mode

```python
--8<-- "docs/examples/features/masking/masking_merge_mode.py:setup"
--8<-- "docs/examples/features/masking/masking_merge_mode.py:example"
```

```title="Error"
--8<-- "docs/examples/features/masking/masking_merge_mode.stderr"
```

### Global

See [Configure](configure.md#global-configure) for global masking defaults and all available config options.
