# ENV Variable Expansion

String values in all file formats support environment variable expansion:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion.py:setup"
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion.py:example"
    ```

=== "advanced_env_expansion.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/env_expansion/sources/advanced_env_expansion.yaml"
    ```

## Supported Syntax

| Syntax | Description |
|--------|-------------|
| `$VAR` | Subsitute variable |
| `${VAR}` | Substitute variable (alterative form) |
| `${VAR:-default}` | Variable with fallback value |
| `${VAR:-$FALLBACK_VAR}` | Fallback is also an env variable |
| `%VAR%` | Substitute variable (alterative windows-like form) |
| `$$` | Literal `$` (escaped) |
| `%%` | Literal `%` (escaped) |

## Expansion Modes

| Mode | Missing variable |
|------|------------------|
| `"default"` | Kept as-is (`$VAR` stays `$VAR`) |
| `"empty"` | Replaced with `""` |
| `"strict"` | Raises `EnvVarExpandError` |
| `"disabled"` | No expansion at all |

The `"default"` mode is named so because it matches the behavior of Python's built-in `os.path.expandvars()` — missing variables are kept as-is rather than being replaced with empty strings or raising errors.

Set the mode on `Source`:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_strict.py:setup"
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_strict.py:example"
    ```

=== "advanced_env_expansion_strict.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/env_expansion/sources/advanced_env_expansion_strict.yaml"
    ```

For merge mode, pass `expand_env_vars` to `dature.load()` as default for all sources:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_merge.py:setup"
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_merge.py:example"
    ```

=== "advanced_env_expansion_merge_default.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/env_expansion/sources/advanced_env_expansion_merge_default.yaml"
    ```

=== "advanced_env_expansion_merge_empty.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/env_expansion/sources/advanced_env_expansion_merge_empty.yaml"
    ```

=== "advanced_env_expansion_merge_disabled.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/env_expansion/sources/advanced_env_expansion_merge_disabled.yaml"
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

Environment variables in the `file=...` parameter of Source subclasses are expanded automatically in `"strict"` mode — if a variable is missing, `EnvVarExpandError` is raised immediately at Source creation time.

This works for both directory paths and file names:

=== "Variable in directory path"

    ```python
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_file_path_dir.py:setup"
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_file_path_dir.py:example"
    ```

=== "Variable in file name"

    ```python
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_file_path_name.py:setup"
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_file_path_name.py:example"
    ```

=== "Both"

    ```python
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_file_path_combined.py:setup"
    --8<-- "docs/examples/advanced/env_expansion/advanced_env_expansion_file_path_combined.py:example"
    ```

All [supported syntax](#supported-syntax) (`$VAR`, `${VAR}`, `${VAR:-default}`, `%VAR%`) works in file paths.

`str` and `Path` values are both expanded. File-like objects and `None` are passed through unchanged.

!!! note
    File path expansion is always `"strict"`, independent of the `expand_env_vars` setting. The `expand_env_vars` parameter controls expansion of values **inside** config files, while file paths are expanded at `Source` creation time. A missing variable in a file path would lead to a confusing `FileNotFoundError`, so strict validation is enforced.


