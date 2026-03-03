# Introduction

dature offers two ways to load configuration: **function mode** and **decorator mode**.

## Function Mode

Call `load()` with a `LoadMetadata` descriptor and a dataclass type:

=== "app.yaml"

    ```yaml
    --8<-- "examples/docs/sources/app.yaml"
    ```

=== "Python"

    ```python
    --8<-- "examples/docs/format_yaml.py"
    ```

## Decorator Mode

Use `@load()` as a decorator. The dataclass auto-loads on every instantiation:

=== "app.yaml"

    ```yaml
    --8<-- "examples/docs/sources/app.yaml"
    ```

=== "Python"

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
@dataclass(frozen=True, slots=True, kw_only=True)
class LoadMetadata:
    file_: str | None = None
    loader: type[LoaderProtocol] | None = None
    prefix: DotSeparatedPath | None = None
    split_symbols: str = "__"
    name_style: NameStyle | None = None
    field_mapping: FieldMapping | None = None
    root_validators: tuple[ValidatorProtocol, ...] | None = None
    validators: FieldValidators | None = None
    expand_env_vars: ExpandEnvVarsMode | None = None
    skip_if_broken: bool | None = None
    skip_if_invalid: bool | tuple[FieldPath, ...] | None = None
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
```

| Parameter | Description |
|-----------|-------------|
| `file_` | Path to config file or directory. `None` → environment variables |
| `loader` | Explicit loader class. `None` → auto-detect from extension |
| `prefix` | Filter ENV keys (`"APP_"`) or extract nested object (`"app.database"`) |
| `split_symbols` | Delimiter for flat→nested conversion. Default: `"__"` |
| `name_style` | Naming convention mapping. See [Naming](naming.md) |
| `field_mapping` | Explicit field renaming with `F` objects. See [Naming](naming.md) |
| `root_validators` | Post-load validation of the entire object. See [Validation](validation.md) |
| `validators` | Per-field validators in metadata. See [Validation](validation.md) |
| `expand_env_vars` | ENV variable expansion mode. See [Advanced](advanced.md#env-variable-expansion) |
| `skip_if_broken` | Skip this source if it fails to load. See [Merging — Skipping Broken Sources](merging.md#skipping-broken-sources) |
| `skip_if_invalid` | Skip invalid fields from this source. See [Merging — Skipping Invalid Fields](merging.md#skipping-invalid-fields) |
| `secret_field_names` | Extra secret name patterns for masking. See [Masking](masking.md) |
| `mask_secrets` | Enable/disable secret masking for this source. See [Masking — Configuration](masking.md#configuration) |

## Type Coercion

String values from ENV and file formats are automatically converted:

| Source | Target | Example |
|--------|--------|---------|
| `"42"` | `int` | `42` |
| `"3.14"` | `float` | `3.14` |
| `"true"` | `bool` | `True` |
| `"2024-01-15"` | `date` | `date(2024, 1, 15)` |
| `"2024-01-15T10:30:00"` | `datetime` | `datetime(...)` |
| `"10:30:00"` | `time` | `time(10, 30)` |
| `"1 day, 2:30:00"` | `timedelta` | `timedelta(...)` |
| `"1+2j"` | `complex` | `(1+2j)` |
| `"192.168.1.1"` | `IPv4Address` | `IPv4Address(...)` |
| `"[1, 2, 3]"` | `list[int]` | `[1, 2, 3]` |

Nested dataclasses, `Optional`, and `Union` types are also supported.

## Error Messages

dature provides human-readable error messages with source location:

```
Config loading errors (2)

  [database.host]  Missing required field
   └── FILE 'config.json', line 2-5
       "database": {
         "host": "localhost",
         "port": 5432
       }

  [port]  Expected int, got str
   └── ENV 'APP_PORT'
```

Docker secrets errors point to the secret file:

```
Config loading errors (1)

  [password]  Missing required field
   └── SECRET FILE '/run/secrets/password'
```
