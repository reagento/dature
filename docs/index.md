# dature

**Type-safe configuration loader for Python dataclasses.**

Load config from YAML, JSON, TOML, INI, ENV files, environment variables and Docker secrets with automatic type conversion, validation and human-readable error messages.

---

## Features

- **Type-safe** — automatic conversion from strings to all Python types (`int`, `float`, `bool`, `date`, `datetime`, `Enum`, `IPv4Address`, etc.) and nested dataclasses
- **Multiple formats** — YAML (1.1, 1.2), JSON, JSON5, TOML (1.0, 1.1), INI, ENV, Docker secrets, environment variables
- **Merge sources** — combine defaults, overrides, and env vars with configurable strategies
- **Validation** — built-in validators via `Annotated`, root validators, custom validators
- **Secret masking** — auto-detect and mask secrets in errors, logs, and debug reports
- **Human-readable errors** — source location, line numbers, and formatted context
- **Two modes** — function call or decorator with caching

## Installation

=== "pip"

    ```bash
    pip install dature
    ```

=== "uv"

    ```bash
    uv add dature
    ```

=== "poetry"

    ```bash
    poetry add dature
    ```

### Optional format support

=== "pip"

    ```bash
    pip install dature[yaml]    # YAML support (ruamel.yaml)
    pip install dature[json5]   # JSON5 support
    pip install dature[toml]    # TOML support (toml_rs)
    pip install dature[secure]  # Secret detection heuristics
    ```

    Install everything:

    ```bash
    pip install dature[yaml,json5,toml,secure]
    ```

=== "uv"

    ```bash
    uv add dature[yaml]    # YAML support (ruamel.yaml)
    uv add dature[json5]   # JSON5 support
    uv add dature[toml]    # TOML support (toml_rs)
    uv add dature[secure]  # Secret detection heuristics
    ```

    Install everything:

    ```bash
    uv add dature[yaml,json5,toml,secure]
    ```

=== "poetry"

    ```bash
    poetry add dature[yaml]    # YAML support (ruamel.yaml)
    poetry add dature[json5]   # JSON5 support
    poetry add dature[toml]    # TOML support (toml_rs)
    poetry add dature[secure]  # Secret detection heuristics
    ```

    Install everything:

    ```bash
    poetry add dature[yaml,json5,toml,secure]
    ```

## Quick Start

=== "Function mode"

    ```python
    --8<-- "examples/docs/intro_function.py"
    ```

=== "Decorator mode"

    ```python
    --8<-- "examples/docs/intro_decorator.py"
    ```

## Supported Formats

| Format | Extension | Loader | Extra dependency |
|--------|-----------|--------|------------------|
| YAML 1.1 | `.yaml`, `.yml` | `Yaml11Loader` | `ruamel.yaml` |
| YAML 1.2 | `.yaml`, `.yml` | `Yaml12Loader` | `ruamel.yaml` |
| JSON | `.json` | `JsonLoader` | — |
| JSON5 | `.json5` | `Json5Loader` | `json-five` |
| TOML 1.0 | `.toml` | `Toml10Loader` | `toml-rs` |
| TOML 1.1 | `.toml` | `Toml11Loader` | `toml-rs` |
| INI | `.ini`, `.cfg` | `IniLoader` | — |
| ENV file | `.env` | `EnvFileLoader` | — |
| Environment variables | — | `EnvLoader` | — |
| Docker secrets | directory | `DockerSecretsLoader` | — |

The format is auto-detected from the file extension. When `file_` is not specified, environment variables are used. When `file_` points to a directory, `DockerSecretsLoader` is used.

## What's Next

- [Introduction](introduction.md) — function vs decorator mode, all formats, LoadMetadata reference
- [Naming](naming.md) — name_style, field_mapping, prefix, split_symbols
- [Validation](validation.md) — Annotated validators, root validators, custom validators
- [Merging](merging.md) — multiple sources, strategies, field groups
- [Masking](masking.md) — SecretStr, auto-detection, configuration
- [Advanced](advanced.md) — per-field merge rules, debug reports, ENV expansion, special types
- [API Reference](api-reference.md) — full API documentation
