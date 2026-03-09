# Introduction

dature offers two ways to load configuration: **function mode** and **decorator mode**.

=== "Function mode"

    Call `load()` with a `LoadMetadata` descriptor and a dataclass type:

    ```yaml title="app.yaml"
    --8<-- "examples/docs/sources/app.yaml"
    ```

    ```python
    --8<-- "examples/docs/format_yaml.py"
    ```

=== "Decorator mode"

    Use `@load()` as a decorator. The dataclass auto-loads on every instantiation:

    ```yaml title="app.yaml"
    --8<-- "examples/docs/sources/app.yaml"
    ```

    ```python
    --8<-- "examples/docs/intro_decorator_file.py"
    ```

    Explicit arguments to `__init__` take priority over loaded values:

    ```python
    config = Config(port=9090)  # host from source, port overridden
    ```

## All Formats

dature auto-detects the format from the file extension. Here's the same config loaded from every supported format:

=== "YAML"

    ```yaml title="app.yaml"
    --8<-- "examples/docs/sources/app.yaml"
    ```

    ```python
    --8<-- "examples/docs/format_yaml.py"
    ```

=== "JSON"

    ```json title="app.json"
    --8<-- "examples/docs/sources/app.json"
    ```

    ```python
    --8<-- "examples/docs/format_json.py"
    ```

=== "JSON5"

    ```json5 title="app.json5"
    --8<-- "examples/docs/sources/app.json5"
    ```

    ```python
    --8<-- "examples/docs/format_json5.py"
    ```

=== "TOML"

    ```toml title="app.toml"
    --8<-- "examples/docs/sources/app.toml"
    ```

    ```python
    --8<-- "examples/docs/format_toml.py"
    ```

=== "INI"

    ```ini title="app.ini"
    --8<-- "examples/docs/sources/app.ini"
    ```

    ```python
    --8<-- "examples/docs/format_ini.py"
    ```

=== "ENV"

    ```bash title="app.env"
    --8<-- "examples/docs/sources/app.env"
    ```

    ```python
    --8<-- "examples/docs/format_env.py"
    ```

=== "Docker Secrets"

    ```
    app_docker_secrets/
    ├── host    → "localhost"
    ├── port    → "8080"
    └── debug   → "false"
    ```

    ```python
    --8<-- "examples/docs/format_docker.py"
    ```

### Auto-Detection

| Extension | Loader |
|-----------|--------|
| `.yaml`, `.yml` | `Yaml12Loader` (default) |
| `.json` | `JsonLoader` |
| `.json5` | `Json5Loader` |
| `.toml` | `Toml11Loader` (default) |
| `.ini`, `.cfg` | `IniLoader` |
| `.env` | `EnvFileLoader` |
| directory | `DockerSecretsLoader` |
| not specified | `EnvLoader` (environment variables) |

Override auto-detection with the `loader` parameter:

```python
from dature.sources_loader.yaml_ import Yaml11Loader

LoadMetadata(file_="config.yaml", loader=Yaml11Loader)
```

## LoadMetadata Reference

```python
--8<-- "src/dature/metadata.py:load-metadata"
```

| Parameter | Description |
|-----------|-------------|
| `file_` | Path to config file (`str`, `Path`), file-like object (`BytesIO`, `StringIO`), or directory. `None` → environment variables. File-like objects require explicit `loader` |
| `loader` | Explicit loader class. `None` → auto-detect from extension |
| `prefix` | Filter ENV keys (`"APP_"`) or extract nested object (`"app.database"`) |
| `split_symbols` | Delimiter for flat→nested conversion. Default: `"__"` |
| `name_style` | Naming convention mapping. See [Naming](features/naming.md) |
| `field_mapping` | Explicit field renaming with `F` objects. See [Naming](features/naming.md) |
| `root_validators` | Post-load validation of the entire object. See [Validation](features/validation.md) |
| `validators` | Per-field validators in metadata. See [Validation](features/validation.md) |
| `expand_env_vars` | ENV variable expansion mode. See [Advanced — ENV Expansion](advanced/env-expansion.md) |
| `skip_if_broken` | Skip this source if it fails to load. See [Advanced — Skipping Broken Sources](advanced/merge-rules.md#skipping-broken-sources) |
| `skip_if_invalid` | Skip invalid fields from this source. See [Advanced — Skipping Invalid Fields](advanced/merge-rules.md#skipping-invalid-fields) |
| `secret_field_names` | Extra secret name patterns for masking. See [Masking](features/masking.md) |
| `mask_secrets` | Enable/disable secret masking for this source. See [Masking](features/masking.md) |

### File-Like Objects

`file_` accepts file-like objects (`StringIO`, `BytesIO`, and any `TextIOBase`/`BufferedIOBase`/`RawIOBase` subclass). The `loader` parameter is required since there is no file extension to auto-detect from:

```python
--8<-- "examples/docs/intro_file_like.py"
```

!!! note
    `EnvLoader` and `DockerSecretsLoader` do not support file-like objects — they read from environment variables and directories respectively.

## Type Coercion

String values from ENV and file formats are automatically converted.

All supported types in one dataclass:

```python
--8<-- "examples/all_types_dataclass.py"
```

### Coercion by Source

Different formats store values differently. YAML, JSON and TOML parse some types natively, while ENV and INI treat everything as strings:

=== "YAML"

    ```yaml
    --8<-- "examples/sources/all_types_yaml12.yaml"
    ```

=== "JSON"

    ```json
    --8<-- "examples/sources/all_types.json"
    ```

=== "TOML"

    ```toml
    --8<-- "examples/sources/all_types_toml11.toml"
    ```

=== "INI"

    ```ini
    --8<-- "examples/sources/all_types.ini"
    ```

=== "ENV"

    ```bash
    --8<-- "examples/sources/all_types.env"
    ```

## Error Messages

dature provides human-readable error messages with source location and context:

=== "YAML"

    ```
    Config loading errors (1)

      [port]  Bad string format
       └── FILE 'config.yaml', line 2
           port: "abc"
    ```

=== "JSON"

    ```
    Config loading errors (1)

      [port]  Bad string format
       └── FILE 'config.json', line 2
           "port": "abc"
    ```

=== "TOML"

    ```
    Config loading errors (1)

      [port]  Bad string format
       └── FILE 'config.toml', line 2
           port = "abc"
    ```

=== "INI"

    ```
    Config loading errors (1)

      [port]  Bad string format
       └── FILE 'config.ini', line 2
           port = abc
    ```

=== "ENV file"

    ```
    Config loading errors (1)

      [port]  Bad string format
       └── ENV FILE '.env', line 1
           PORT=abc
    ```

=== "ENV variables"

    ```
    Config loading errors (1)

      [port]  Bad string format
       └── ENV 'APP_PORT'
    ```

=== "Docker Secrets"

    ```
    Config loading errors (1)

      [password]  Missing required field
       └── SECRET FILE '/run/secrets/password'
    ```
