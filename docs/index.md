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
    --8<-- "examples/docs/index/intro_function.py"
    ```

=== "Decorator mode"

    ```python
    --8<-- "examples/docs/index/intro_decorator.py"
    ```

## Supported Formats

| Format | Source Class | Extra dependency |
|--------|--------------|------------------|
| YAML 1.1 | `Yaml11Source` | `ruamel.yaml` |
| YAML 1.2 | `Yaml12Source` | `ruamel.yaml` |
| JSON | `JsonSource` | — |
| JSON5 | `Json5Source` | `json-five` |
| TOML 1.0 | `Toml10Source` | `toml-rs` |
| TOML 1.1 | `Toml11Source` | `toml-rs` |
| INI | `IniSource` | — |
| ENV file | `EnvFileSource` | — |
| Environment variables | `EnvSource` | — |
| Docker secrets | `DockerSecretsSource` | — |

Use the specific Source subclass for your format. File-based sources (`FileSource` subclasses) accept `file` as `str`, `Path`, or file-like object (`BytesIO`, `StringIO`). `EnvSource` reads from environment variables (no `file` parameter). `DockerSecretsSource` accepts `dir` pointing to a secrets directory.

## mypy Plugin

When using `@dature.load()` as a decorator, mypy will report `call-arg` errors because the original dataclass `__init__` still requires all fields. dature ships with a mypy plugin that makes all fields optional in decorated classes:

```toml
[tool.mypy]
plugins = ["dature.mypy_plugin"]
```

## What's Next

- [Introduction](introduction.md) — function vs decorator mode, all formats, Source reference
- [Naming](features/naming.md) — name_style, field_mapping, prefix, nested_sep
- [Validation](features/validation.md) — Annotated validators, root validators, custom validators
- [Merging](features/merging.md) — multiple sources, strategies, field groups
- [Masking](features/masking.md) — SecretStr, auto-detection, configuration
- [API Reference](api-reference.md) — full API documentation
