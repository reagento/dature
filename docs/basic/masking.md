# Masking

dature automatically masks values in error messages, debug logs, and `LoadReport` to prevent accidental leakage of sensitive data.

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

## Modes

`MaskingConfig.masking_mode` controls how aggressively values are masked:

| Mode | Behavior |
|------|----------|
| `all` (default) | Every string value is masked, regardless of field name or type |
| `secrets_only` | Only fields matched by name, type, or heuristic are masked (see [Detection Methods](#detection-methods) below) |
| `none` | No masking at all |

The default is `all` — a value never appears in the clear unless you explicitly opt into a narrower
mode. Each mode below loads the same config, where `host` holds an invalid value and is therefore
the one shown in the error — watch how its value changes across modes:

```yaml title="masking_mode.yaml"
--8<-- "docs/examples/basic/masking/sources/masking_mode.yaml"
```

=== "all (default)"

    Every string value is masked, including `host` — even though its name matches no secret pattern:

    ```python
    --8<-- "docs/examples/basic/masking/masking_mode_all.py:example"
    ```

    ```title="Error"
    --8<-- "docs/examples/basic/masking/masking_mode_all.stderr"
    ```

=== "secrets_only"

    Only fields matched by name, type, or heuristic are masked. `host` is not one of them, so it
    appears unmasked:

    ```python
    --8<-- "docs/examples/basic/masking/masking_mode_secrets_only.py:example"
    ```

    ```title="Error"
    --8<-- "docs/examples/basic/masking/masking_mode_secrets_only.stderr"
    ```

=== "none"

    Masking is disabled entirely — every value, secret or not, appears in the clear:

    ```python
    --8<-- "docs/examples/basic/masking/masking_mode_none.py:example"
    ```

    ```title="Error"
    --8<-- "docs/examples/basic/masking/masking_mode_none.stderr"
    ```

## Detection Methods (`masking_mode="secrets_only"`)

With `masking_mode="secrets_only"`, dature uses three methods to identify secrets:

| Method | Description | Always active |
|--------|-------------|---------------|
| **By type** | Fields typed as `SecretStr` or `PaymentCardNumber` | Yes |
| **By name** | Field name contains a known pattern (case-insensitive) | Yes |
| **Heuristic** | String values that look like random tokens | Requires `dature[secure]` |

### Default Name Patterns

`password`, `passwd`, `secret`, `token`, `key`, `auth`, `credential`, `uri`, `url`

Matching is substring-based and case-insensitive, so this also covers common variants like
`api_key`, `api-key`, `apikey`, `access_key`, `private-key`, `secret-key`, `connection_uri`, and
`service_url`.

### Name-Style and `field_mapping` Awareness

Secret detection is based on dataclass field names (e.g. `secret_key`), but matching against a
source's raw keys is case/separator-insensitive, so a source's `name_style` (`lower_kebab`,
`upperCamel`, etc.) never hides a secret field — `secret_key`, `secret-key`, `secretKey`, and
`SECRET_KEY` are all recognized as the same field. Keys in error messages, debug logs, and
`LoadReport` are always shown exactly as they appear in the source — only the *value* is masked,
never the key spelling.

If a field is secret by type (`SecretStr`, `PaymentCardNumber`) or by name, and you alias it via
`field_mapping` to a name that doesn't itself look secret (e.g. mapping a `SecretStr` field to
`DATABASE_HOSTNAME`), the alias is masked too. This is the one case name-style normalization can't
cover on its own, since the alias is an arbitrary string chosen by you, not a case/separator
variant of the field name.

`secret_field_names` passed to `dature.load()` extends by-name detection for **schema fields**
only. To also mask non-schema raw keys (e.g. entries inside a `dict[str, str]` field) that match a
custom pattern under `masking_mode="secrets_only"`, set the pattern globally instead:
`dature.configure(masking={"secret_field_names": (...)})`.

## Examples

=== "By type (SecretStr, PaymentCardNumber)"

    `SecretStr` and `PaymentCardNumber` mask values in `str()`, `repr()`, and debug logs:

    ```python
    --8<-- "docs/examples/basic/masking/masking_secret_str.py:example"
    ```

    ```yaml title="masking_secret_str.yaml"
    --8<-- "docs/examples/basic/masking/sources/masking_secret_str.yaml"
    ```

    ```title="Error"
    --8<-- "docs/examples/basic/masking/masking_secret_str.stderr"
    ```

=== "By name"

    Fields whose names contain known patterns are automatically masked in error messages:

    ```python
    --8<-- "docs/examples/basic/masking/masking_by_name.py:example"
    ```

    ```yaml title="masking_by_name.yaml"
    --8<-- "docs/examples/basic/masking/sources/masking_by_name.yaml"
    ```

    ```title="Error"
    --8<-- "docs/examples/basic/masking/masking_by_name.stderr"
    ```

=== "Heuristic"

    With `dature[secure]`, values that look like random tokens are masked in error messages even if the field name is not a known secret pattern:

    ```python
    --8<-- "docs/examples/basic/masking/masking_heuristic.py:example"
    ```

    ```yaml title="masking_heuristic.yaml"
    --8<-- "docs/examples/basic/masking/sources/masking_heuristic.yaml"
    ```

    ```title="Error"
    --8<-- "docs/examples/basic/masking/masking_heuristic.stderr"
    ```

## Mask Format

By default, the entire value is replaced with `<REDACTED>`:

- `"my_secret_password"` → `"<REDACTED>"`
- `"1234"` → `"<REDACTED>"`

Configure `visible_prefix` / `visible_suffix` to keep characters visible at the start/end:

If `visible_prefix + visible_suffix >= len(value)`, the value is shown as-is.

Classic `ab*****cd` style:

```python
--8<-- "docs/examples/basic/masking/masking_classic_style.py:example"
```
* `"my_secret_password"` → `"my*****rd"`
* `"ab"` → `"ab"` (too short — shown as-is)

## Configuration

### Per-load

`masking_mode` and `secret_field_names` are passed directly to `dature.load()`. They apply to both single-source and multi-source modes.

=== "masking_mode=\"none\""

    ```python
    --8<-- "docs/examples/basic/masking/masking_no_mask.py:example"
    ```

    ```title="Error"
    --8<-- "docs/examples/basic/masking/masking_no_mask.stderr"
    ```

### In merge mode

```python
--8<-- "docs/examples/basic/masking/masking_merge_mode.py:example"
```

```title="Error"
--8<-- "docs/examples/basic/masking/masking_merge_mode.stderr"
```

### Global

See [Configure](configure.md#global-configure) for global masking defaults and all available config options.
