# ENV Variable Expansion

String values in all file formats support environment variable expansion:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/env_expansion/advanced_env_expansion.py"
    ```

=== "advanced_env_expansion.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/env_expansion/sources/advanced_env_expansion.yaml"
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

Set the mode on `Source`:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/env_expansion/advanced_env_expansion_strict.py"
    ```

=== "advanced_env_expansion_strict.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/env_expansion/sources/advanced_env_expansion_strict.yaml"
    ```

For merge mode, set on `Merge` as default for all sources:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/env_expansion/advanced_env_expansion_merge.py"
    ```

=== "advanced_env_expansion_merge_default.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/env_expansion/sources/advanced_env_expansion_merge_default.yaml"
    ```

=== "advanced_env_expansion_merge_empty.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/env_expansion/sources/advanced_env_expansion_merge_empty.yaml"
    ```

=== "advanced_env_expansion_merge_disabled.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/env_expansion/sources/advanced_env_expansion_merge_disabled.yaml"
    ```

In `"strict"` mode, all missing variables are collected and reported at once:

=== "YAML"

    ```
    Config env expand errors (1)

      [host]  Missing environment variable 'MISSING_HOST'
       └── FILE 'config.yaml', line 1
           host: "$MISSING_HOST"
    ```

=== "JSON"

    ```
    Config env expand errors (1)

      [host]  Missing environment variable 'MISSING_HOST'
       └── FILE 'config.json', line 1
           {"host": "$MISSING_HOST", "port": 8080}
    ```

=== "TOML"

    ```
    Config env expand errors (1)

      [host]  Missing environment variable 'MISSING_HOST'
       └── FILE 'config.toml', line 1
           host = "$MISSING_HOST"
    ```

=== "INI"

    ```
    Config env expand errors (1)

      [host]  Missing environment variable 'MISSING_HOST'
       └── FILE 'config.ini', line 2
           host = $MISSING_HOST
    ```

=== "ENV file"

    ```
    Config env expand errors (1)

      [host]  Missing environment variable 'MISSING_HOST'
       └── ENV FILE 'config.env', line 1
           HOST=$MISSING_HOST
    ```

The `${VAR:-default}` fallback syntax works in all modes.

## File Path Expansion

Environment variables in `Source(file_=...)` are expanded automatically in `"strict"` mode — if a variable is missing, `EnvVarExpandError` is raised immediately at `Source` creation time.

This works for both directory paths and file names:

=== "Variable in directory path"

    ```python
    --8<-- "examples/docs/advanced/env_expansion/advanced_env_expansion_file_path_dir.py"
    ```

=== "Variable in file name"

    ```python
    --8<-- "examples/docs/advanced/env_expansion/advanced_env_expansion_file_path_name.py"
    ```

=== "Both"

    ```python
    --8<-- "examples/docs/advanced/env_expansion/advanced_env_expansion_file_path_combined.py"
    ```

All [supported syntax](#supported-syntax) (`$VAR`, `${VAR}`, `${VAR:-default}`, `%VAR%`) works in file paths.

`str` and `Path` values are both expanded. File-like objects and `None` are passed through unchanged.
