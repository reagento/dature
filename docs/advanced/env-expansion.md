# ENV Variable Expansion

String values in all file formats support environment variable expansion:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_env_expansion.py"
    ```

=== "env_expand.yaml"

    ```yaml
    --8<-- "examples/docs/sources/env_expand.yaml"
    ```

## Supported Syntax

| Syntax | Description |
|--------|-------------|
| `$VAR` | Simple variable |
| `${VAR}` | Braced variable |
| `${VAR:-default}` | Variable with fallback value |
| `${VAR:-$FALLBACK_VAR}` | Fallback is also an env variable |
| `%VAR%` | Windows-style variable |
| `$$` | Literal `$` (escaped) |
| `%%` | Literal `%` (escaped) |

## Expansion Modes

| Mode | Missing variable |
|------|------------------|
| `"default"` | Kept as-is (`$VAR` stays `$VAR`) |
| `"empty"` | Replaced with `""` |
| `"strict"` | Raises `EnvVarExpandError` |
| `"disabled"` | No expansion at all |

Set the mode on `LoadMetadata`:

```python
config = load(LoadMetadata(file_="config.yaml", expand_env_vars="strict"), Config)
```

For merge mode, set on `MergeMetadata` as default for all sources:

```python
config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_="defaults.yaml"),
            LoadMetadata(file_="overrides.yaml", expand_env_vars="disabled"),  # override per source
        ),
        expand_env_vars="strict",  # default for all sources
    ),
    Config,
)
```

In `"strict"` mode, all missing variables are collected and reported at once:

```
Missing environment variables (2):
  - DATABASE_URL (position 0 in '$DATABASE_URL')
  - SECRET_KEY (position 0 in '${SECRET_KEY}')
```

The `${VAR:-default}` fallback syntax works in all modes.
