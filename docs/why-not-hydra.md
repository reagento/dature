# Why Not Hydra?

[Hydra](https://hydra.cc/) (by Meta Research) is a popular configuration framework in the ML world. It shines at composing YAML configs with overrides from the command line. If your workflow is "train a model with 50 hyperparameter combinations" — Hydra was built for that.

But for **application configuration** — web services, data pipelines, microservices — Hydra's design becomes a burden. dature is built for this use case from the ground up.

## Side-by-Side

| | Hydra | dature |
|---|---|---|
| **Config definition** | YAML files + `@dataclass` structured configs | stdlib `@dataclass` — single source of truth |
| **Formats** | YAML only | YAML, JSON, JSON5, TOML, INI, `.env`, env vars, Docker secrets |
| **Env variables** | Not built-in (community plugins) | First-class: env vars, `.env` files, `${VAR:-default}` expansion in all formats |
| **Docker secrets** | No | Built-in `DockerSecretsLoader` |
| **Merging** | Composition via defaults list | 4 strategies + per-field rules (`APPEND`, `PREPEND`, field groups, etc.) |
| **Validation** | Basic type checking via OmegaConf | `Annotated` validators, root validators, custom validators |
| **Error messages** | OmegaConf exceptions | Human-readable: source file, line number, context snippet |
| **Secret masking** | No | Auto-masks secrets in errors and logs |
| **Type support** | Primitives, enums, basic containers | Primitives, `datetime`, `IPv4Address`, `Enum`, `SecretStr`, `ByteSize`, nested dataclasses, and more |
| **Union types** | Not supported | Supported |
| **Debug / audit** | No | `debug=True` — which source provided each value |
| **Dependencies** | `hydra-core` + `omegaconf` + `antlr4-runtime` | `adaptix` (pure Python) |
| **Maintenance** | Last release: Dec 2022. [Acknowledged as unmaintained](https://github.com/facebookresearch/xformers/issues/848) by other Meta teams | Active development |

## YAML-Only vs. Real-World Formats

Hydra only reads YAML. For application configuration this is a serious limitation:

- **Environment variables** — the standard for containers and CI/CD. Hydra has no built-in support; you need community plugins or OmegaConf resolvers.
- **`.env` files** — ubiquitous in local development. Not supported.
- **TOML** — the standard for Python packaging (`pyproject.toml`), gaining popularity for app config. Not supported.
- **Docker secrets** — mounted as files at `/run/secrets/`. Not supported.

dature handles all of these out of the box, with auto-detection from file extension:

```python
from dature import load, MergeMetadata, LoadMetadata

config = load(
    MergeMetadata(
        LoadMetadata(file_="defaults.yaml"),
        LoadMetadata(file_="config.toml", skip_if_broken=True),
        LoadMetadata(file_=".env", skip_if_broken=True),
        LoadMetadata(prefix="APP_"),  # env vars
    ),
    Config,
)
```

## OmegaConf Is Not a Dataclass

Hydra wraps your config in `OmegaConf.DictConfig` — a special container that looks like a dataclass but isn't:

```python
# Hydra
@hydra.main(config_path="conf", config_name="config")
def app(cfg: DictConfig) -> None:
    # cfg is OmegaConf DictConfig, not your dataclass
    # isinstance(cfg, YourConfig) → False
    # No IDE autocompletion for fields
    # No type safety at runtime
    pass
```

dature returns **your actual dataclass**:

```python
# dature
config = load(LoadMetadata(file_="config.yaml"), Config)
# isinstance(config, Config) → True
# Full IDE support, type safety, __post_init__ works
```

## The `@hydra.main` Problem

Hydra takes over your application entry point. The `@hydra.main` decorator:

- **Changes your working directory** — every run creates a new output dir. Your relative paths break.
- **Controls logging** — replaces your logging configuration.
- **Manages the output directory** — creates `outputs/YYYY-MM-DD/HH-MM-SS/` structure whether you want it or not.

This is useful for ML experiments. For a web service, it's hostile.

dature is a **library, not a framework** — it loads config and returns a dataclass. No side effects, no directory changes, no logging hijack.

## Weak Validation

OmegaConf validates types but not values. Need to check that a port is between 1 and 65535? That a URL is valid? That a string matches a pattern?

```python
# Hydra/OmegaConf — no built-in value validation
@dataclass
class Config:
    port: int = 8080  # Any int is accepted, even -1
```

dature uses `Annotated` validators:

```python
from dataclasses import dataclass
from typing import Annotated
from dature import load, LoadMetadata
from dature.validators import Gt, Lt

@dataclass
class Config:
    port: Annotated[int, Gt(0), Lt(65536)] = 8080
```

Plus root validators for cross-field checks, custom validators, and standard `__post_init__`.

## Unmaintained

Hydra's last release (1.3.0) was in **December 2022**. Issues accumulate without maintainer response. Other Meta projects have moved away from it. The `hydra-zen` community project fills some gaps, but the core framework is effectively frozen.

dature is under active development with a clear roadmap: remote sources (Vault, AWS SSM), built-in caching, and config watching.

## When to Use Hydra

Hydra is still a reasonable choice if:

- You're running ML experiments with many hyperparameter sweeps
- Your config is YAML-only and you need composition via defaults lists
- You want CLI overrides like `python train.py model.lr=0.001`
- You're already deep in the Hydra ecosystem (`hydra-zen`, `lightning-hydra-template`)

For **application configuration** — dature.
