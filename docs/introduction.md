# Introduction

dature offers two ways to load configuration: **function mode** and **decorator mode**.

=== "Function mode"

    ```yaml title="common_app.yaml"
    --8<-- "docs/examples/shared/common_app.yaml"
    ```

    ```python
    --8<-- "docs/examples/introduction/format_yaml.py:example"
    ```

=== "Decorator mode"

    ```yaml title="common_app.yaml"
    --8<-- "docs/examples/shared/common_app.yaml"
    ```

    ```python
    --8<-- "docs/examples/introduction/intro_decorator_file.py:example"
    ```

    Explicit arguments to `__init__` take priority over loaded values:

    ```python
    --8<-- "docs/examples/introduction/intro_decorator_override.py:example"
    ```

## All Formats

Use the specific Source subclass for your format. Here's the same config loaded from every supported format:

=== "YAML"

    ```yaml title="common_app.yaml"
    --8<-- "docs/examples/shared/common_app.yaml"
    ```

    ```python
    --8<-- "docs/examples/introduction/format_yaml.py:example"
    ```

=== "JSON"

    ```json title="intro_app.json"
    --8<-- "docs/examples/introduction/sources/intro_app.json"
    ```

    ```python
    --8<-- "docs/examples/introduction/format_json.py:example"
    ```

=== "JSON5"

    ```json5 title="intro_app.json5"
    --8<-- "docs/examples/introduction/sources/intro_app.json5"
    ```

    ```python
    --8<-- "docs/examples/introduction/format_json5.py:example"
    ```

=== "TOML"

    ```toml title="intro_app.toml"
    --8<-- "docs/examples/introduction/sources/intro_app.toml"
    ```

    ```python
    --8<-- "docs/examples/introduction/format_toml.py:example"
    ```

=== "INI"

    ```ini title="intro_app.ini"
    --8<-- "docs/examples/introduction/sources/intro_app.ini"
    ```

    ```python
    --8<-- "docs/examples/introduction/format_ini.py:example"
    ```

=== "ENV"

    ```bash title="intro_app.env"
    --8<-- "docs/examples/introduction/sources/intro_app.env"
    ```

    ```python
    --8<-- "docs/examples/introduction/format_env.py:example"
    ```

=== "Docker Secrets"

    ```
    app_docker_secrets/
    ├── host    → "localhost"
    ├── port    → "8080"
    └── debug   → "false"
    ```

    ```python
    --8<-- "docs/examples/introduction/format_docker.py:example"
    ```

See the full list of Source classes and their extra dependencies on the [main page](index.md#supported-formats).

## Source Reference

```python
--8<-- "src/dature/sources/base/source.py:load-metadata"
```

| Parameter | Description |
|-----------|-------------|
| `prefix` | Filter ENV keys (`"APP_"`) or extract nested object (`"app.database"`) |
| `name_style` | Naming convention mapping. See [Naming](basic/naming.md) |
| `field_mapping` | Explicit field renaming with `F` objects. See [Naming](basic/naming.md), [Field Paths](basic/field-paths.md) |
| `root_validators` | Post-load validation of the entire object. See [Validation](basic/validation.md) |
| `validators` | Per-field validators in metadata. See [Validation](basic/validation.md) |
| `expand_env_vars` | ENV variable expansion mode. See [Advanced — ENV Expansion](advanced/env-expansion.md) |
| `skip_if_broken` | Skip this source if it fails to parse. See [Skipping Sources with Parse Errors](advanced/skip-behaviors.md#skipping-sources-with-parse-errors) |
| `skip_if_missing` | Skip this source if its file does not exist. See [Skipping Missing Sources](advanced/skip-behaviors.md#skipping-missing-sources) |
| `skip_field_if_invalid` | Skip invalid fields from this source. See [Advanced — Skipping Invalid Fields](advanced/skip-behaviors.md#skipping-invalid-fields) |
| `type_loaders` | Custom type converters for this source. See [Custom Types & Loaders](advanced/custom_types.md#custom-types) |

**FileSource** subclasses (`JsonSource`, `Yaml*Source`, `Toml*Source`, `IniSource`, `Json5Source`) also have:

| Parameter | Description |
|-----------|-------------|
| `file` | Path to config file (`str`, `Path`) or file-like object (`BytesIO`, `StringIO`). `None` → empty path |

**FlatKeySource** subclasses (`EnvSource`, `EnvFileSource`, `DockerSecretsSource`) also have:

| Parameter | Description |
|-----------|-------------|
| `nested_sep` | Delimiter for flat→nested conversion. Default: `"__"` |
| `nested_resolve_strategy` | Priority when both JSON and flat keys exist for a nested field: `"flat"` (default) or `"json"`. See [Nested Resolve](advanced/nested-resolve.md) |
| `nested_resolve` | Per-field strategy overrides using `F` objects — see [Field Paths](basic/field-paths.md). Takes priority over `nested_resolve_strategy`. See [Nested Resolve](advanced/nested-resolve.md#per-field-strategy) |

### File-Like Objects

`file` accepts file-like objects (`StringIO`, `BytesIO`, and any `TextIOBase`/`BufferedIOBase`/`RawIOBase` subclass):

```python
--8<-- "docs/examples/introduction/intro_file_like.py"
```

!!! note
    `EnvSource` and `DockerSecretsSource` do not support file-like objects — they read from environment variables and directories respectively.

## Type Coercion

String values from ENV and file formats are automatically converted. See [Supported Types](supported_types.md) for the full list and [Custom Types & Loaders](advanced/custom_types.md) for custom type parsers and format loaders. Error output with source location is covered in [Validation — Error Format](basic/validation.md#error-format).
