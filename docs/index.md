---
description: >-
  dature is a type-safe configuration loader for Python dataclasses: load config from YAML, JSON, TOML, INI, ENV files, environment variables and Docker secrets with automatic type conversion and human-readable validation errors.
---

# dature — Type-safe configuration loader for Python dataclasses

Load config from YAML, JSON, TOML, INI, ENV files, environment variables, Docker secrets and CLI with automatic type conversion, validation and human-readable error messages.

---

## Features

- **Type-safe** — automatic conversion from strings to all Python types (`int`, `float`, `bool`, `date`, `datetime`, `Enum`, `IPv4Address`, etc.) and nested dataclasses
- **Multiple formats** — YAML (1.1, 1.2), JSON, JSON5, TOML (1.0, 1.1), INI, ENV, Docker secrets, environment variables, CLI
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
    pip install dature[yaml]            # YAML (ruamel.yaml)
    pip install dature[json5]           # JSON5
    pip install dature[toml]            # TOML (toml_rs)
    pip install dature[vault]           # HashiCorp Vault (hvac)
    pip install dature[consul]          # Consul (py-consul)
    pip install dature[etcd]            # etcd (etcd3gw)
    pip install dature[zookeeper]       # Apache ZooKeeper (kazoo)
    pip install dature[aws]             # AWS SSM & Secrets Manager (boto3)
    pip install dature[azure-appconfig] # Azure App Configuration
    pip install dature[azure-keyvault]  # Azure Key Vault
    pip install dature[gcp]             # GCP Secret Manager
    pip install dature[watch]           # File watching for background reload (watchdog)
    pip install dature[secure]          # Secret detection heuristics
    pip install dature[type-stubs]      # Type stubs for the integrations above (mypy/pyright users)
    ```

    Install everything:

    ```bash
    pip install dature[yaml,json5,toml,vault,consul,etcd,zookeeper,aws,azure-appconfig,azure-keyvault,gcp,watch,secure]
    ```

=== "uv"

    ```bash
    uv add dature[yaml]            # YAML (ruamel.yaml)
    uv add dature[json5]           # JSON5
    uv add dature[toml]            # TOML (toml_rs)
    uv add dature[vault]           # HashiCorp Vault (hvac)
    uv add dature[consul]          # Consul (py-consul)
    uv add dature[etcd]            # etcd (etcd3gw)
    uv add dature[zookeeper]       # Apache ZooKeeper (kazoo)
    uv add dature[aws]             # AWS SSM & Secrets Manager (boto3)
    uv add dature[azure-appconfig] # Azure App Configuration
    uv add dature[azure-keyvault]  # Azure Key Vault
    uv add dature[gcp]             # GCP Secret Manager
    uv add dature[watch]           # File watching for background reload (watchdog)
    uv add dature[secure]          # Secret detection heuristics
    uv add dature[type-stubs]      # Type stubs for the integrations above (mypy/pyright users)
    ```

    Install everything:

    ```bash
    uv add dature[yaml,json5,toml,vault,consul,etcd,zookeeper,aws,azure-appconfig,azure-keyvault,gcp,watch,secure]
    ```

=== "poetry"

    ```bash
    poetry add dature[yaml]            # YAML (ruamel.yaml)
    poetry add dature[json5]           # JSON5
    poetry add dature[toml]            # TOML (toml_rs)
    poetry add dature[vault]           # HashiCorp Vault (hvac)
    poetry add dature[consul]          # Consul (py-consul)
    poetry add dature[etcd]            # etcd (etcd3gw)
    poetry add dature[zookeeper]       # Apache ZooKeeper (kazoo)
    poetry add dature[aws]             # AWS SSM & Secrets Manager (boto3)
    poetry add dature[azure-appconfig] # Azure App Configuration
    poetry add dature[azure-keyvault]  # Azure Key Vault
    poetry add dature[gcp]             # GCP Secret Manager
    poetry add dature[watch]           # File watching for background reload (watchdog)
    poetry add dature[secure]          # Secret detection heuristics
    poetry add dature[type-stubs]      # Type stubs for the integrations above (mypy/pyright users)
    ```

    Install everything:

    ```bash
    poetry add dature[yaml,json5,toml,vault,consul,etcd,zookeeper,aws,azure-appconfig,azure-keyvault,gcp,watch,secure]
    ```

## Quick Start

=== "Function mode"

    ```python
    --8<-- "docs/examples/index/intro_function.py"
    ```

=== "Decorator mode"

    ```python
    --8<-- "docs/examples/index/intro_decorator.py"
    ```

## Supported Formats

| Format | Source Class | Extra dependency |
|--------|--------------|------------------|
| YAML 1.1 | [`Yaml11Source`](api-reference.md#yaml11sourcefilesource) | `ruamel.yaml` |
| YAML 1.2 | [`Yaml12Source`](api-reference.md#yaml12sourcefilesource) | `ruamel.yaml` |
| JSON | [`JsonSource`](api-reference.md#jsonsourcefilesource) | — |
| JSON5 | [`Json5Source`](api-reference.md#json5sourcefilesource) | `json-five` |
| TOML 1.0 | [`Toml10Source`](api-reference.md#toml10sourcefilesource) | `toml-rs` |
| TOML 1.1 | [`Toml11Source`](api-reference.md#toml11sourcefilesource) | `toml-rs` |
| INI | [`IniSource`](api-reference.md#inisourcefilesource) | — |
| ENV file | [`EnvFileSource`](api-reference.md#envfilesourceflatkeysource) | — |
| Environment variables | [`EnvSource`](api-reference.md#envsourceflatkeysource) | — |
| Docker secrets | [`DockerSecretsSource`](api-reference.md#dockersecretssourceflatkeysource) | — |
| CLI arguments | [`ArgparseSource`](advanced/cli/argparse.md) ([custom CLI source](advanced/cli/custom.md)) | — |

Use the specific Source subclass for your format. File-based sources (`FileSource` subclasses) accept `file` as `str`, `Path`, or file-like object (`BytesIO`, `StringIO`). `EnvSource` reads from environment variables (no `file` parameter). `DockerSecretsSource` accepts `dir` pointing to a secrets directory.

## mypy Plugin

When using `@dature.load()` as a decorator, mypy will report `call-arg` errors because the original dataclass `__init__` still requires all fields. dature ships with a mypy plugin that makes all fields optional in decorated classes:

```toml
[tool.mypy]
plugins = ["dature.mypy_plugin"]
```

