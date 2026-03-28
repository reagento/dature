# Why Not Hydra?

[Hydra](https://hydra.cc/) (by Meta Research) is a powerful configuration framework built for ML experimentation. Its composition system, CLI overrides, parameter sweeps, and plugin architecture make it the go-to choice for training pipelines with many hyperparameter combinations.

The trade-off is scope: Hydra is a **framework** that takes over your entry point, working directory, and logging. For **application configuration** — web services, data pipelines, microservices — this is too much. dature is a **library** that loads config and returns a dataclass. Nothing else.

## Side-by-Side

| | Hydra | dature |
|---|---|---|
| **Approach** | Framework — takes over entry point, working dir, logging | Library — loads config, returns a dataclass |
| **Config definition** | YAML files + `@dataclass` structured configs | stdlib `@dataclass` — single source of truth |
| **Formats** | YAML only | YAML (1.1/1.2), JSON, JSON5, TOML (1.0/1.1), INI, `.env`, env vars, Docker secrets |
| **Env variables** | `oc.env` resolver; no `.env` support | First-class: env vars, `.env` files, `${VAR:-default}` expansion in all formats + file paths |
| **CLI overrides** | Built-in: `python app.py db.port=3306` + tab completion | No CLI |
| **Composition** | Config groups, defaults list, package overrides | Multi-source merge with explicit strategies |
| **Parameter sweeps** | Built-in multirun + sweeper plugins (Ax, Optuna, etc.) | No — not a use case |
| **Object instantiation** | `instantiate()` — creates objects from config with DI | No — config loading only |
| **Variable interpolation** | OmegaConf `${path.to.key}` + custom resolvers | `${VAR:-default}` env expansion in all formats + file paths |
| **Validation** | Basic type checking via OmegaConf | `Annotated` validators, root validators, custom validators |
| **Type support** | Primitives, enums, basic containers. No Union types | Primitives, `datetime`, `IPv4Address`, `Enum`, `SecretStr`, `ByteSize`, Union types, and more |
| **Error messages** | OmegaConf exceptions | Human-readable: source file, line number, context snippet |
| **Secret masking** | No | Auto-masks secrets in errors and logs |
| **Debug / audit** | Output dir with saved config + logs | `debug=True` — which source provided each value |
| **Plugin system** | Sweepers, launchers, config sources, search path | Custom loaders via `BaseLoader` subclass |
| **Dependencies** | `hydra-core` + `omegaconf` + `antlr4-runtime` | `adaptix` (pure Python) |
| **Config result** | `OmegaConf.DictConfig` (dict-like wrapper) | Your actual `@dataclass` instance |
| **Maintenance** | Last release: Dec 2022. [Acknowledged as unmaintained](https://github.com/facebookresearch/xformers/issues/848) by other Meta teams | Active development |

## YAML-Only vs. Real-World Formats

Hydra reads YAML exclusively. You can reference env vars via OmegaConf's `${oc.env:VAR}` resolver, but there's no native support for:

- **`.env` files** — ubiquitous in local development. Not supported.
- **TOML** — the standard for Python packaging (`pyproject.toml`), increasingly used for app config. Not supported.
- **JSON / JSON5** — common in web services and JavaScript-adjacent tooling. Not supported.
- **INI** — legacy format still common in enterprise. Not supported.

dature handles all of these out of the box, with auto-detection from file extension:

```python
--8<-- "examples/docs/comparison/why-not-hydra/hydra_merge.py:merge"
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
--8<-- "examples/docs/comparison/why-not-hydra/hydra_dataclass.py:dataclass"
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
--8<-- "examples/docs/comparison/why-not-hydra/hydra_validators.py:validators"
```

Plus root validators for cross-field checks, custom validators, and standard `__post_init__`.

And when validation fails, dature underlines the exact problematic value:

```
Config loading errors (1)

  [port]  Value must be greater than 0
   ├── port: -1
   │         ^^
   └── FILE 'config.yaml', line 2
```

Compare with OmegaConf's error for a wrong type:

```
omegaconf.errors.ValidationError: Value 'abc' of type 'str'
could not be converted to Integer
    full_key: port
    object_type=Config
```

No file, no line number, no context.

## What Hydra Does Better

To be fair — Hydra has powerful features designed for ML experimentation that dature doesn't try to replicate:

- **Config composition** — defaults list, config groups, and package overrides let you assemble complex configs from reusable fragments. This is Hydra's killer feature for ML pipelines with many model/dataset/optimizer combinations.
- **CLI overrides** — `python train.py model.lr=0.001 db=postgresql` with tab completion. No code changes needed to override any config value.
- **Parameter sweeps** — built-in multirun mode with sweeper plugins (Ax, Optuna, Nevergrad) for hyperparameter optimization.
- **Object instantiation** — `instantiate()` creates Python objects directly from config with recursive dependency injection.
- **Variable interpolation** — OmegaConf's `${path.to.key}` cross-references within config, plus custom resolvers for computed values.
- **Plugin system** — extensible launchers (local, Submitit, Ray), sweepers, and config sources.
- **Output management** — automatic output directories with saved config, logs, and overrides for each run. Essential for ML experiment tracking.
- **Community ecosystem** — `hydra-zen` (Pythonic config generation), `lightning-hydra-template`, DVC integration.

## Maintenance

Hydra's last release (1.3.0) was in **December 2022**. Issues accumulate without maintainer response. Other Meta projects have [acknowledged it as unmaintained](https://github.com/facebookresearch/xformers/issues/848). The `hydra-zen` community project fills some gaps, but the core framework is effectively frozen.

dature is under active development with a clear roadmap: remote sources (Vault, AWS SSM), built-in caching, and config watching.

## When to Use Hydra

Hydra is still a reasonable choice if:

- You're running ML experiments with many hyperparameter sweeps
- You need config composition via defaults lists and config groups
- You want CLI overrides with tab completion
- You use `instantiate()` to build object graphs from config
- You need output directory management for experiment tracking
- You're already deep in the Hydra ecosystem (`hydra-zen`, `lightning-hydra-template`)

For **application configuration** — dature.
