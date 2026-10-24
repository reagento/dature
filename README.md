<div align="center">

<img src="docs/assets/img/logo.svg" alt="dature" width="400">

---

[![PyPI](https://img.shields.io/pypi/v/dature)](https://pypi.org/project/dature/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/dature)](https://pypi.org/project/dature/)
[![Documentation](https://readthedocs.org/projects/dature/badge/?version=latest)](https://dature.readthedocs.io/)
[![License](https://img.shields.io/github/license/reagento/dature.svg)](https://github.com/reagento/dature/blob/main/LICENSE)
\
[![CI](https://github.com/reagento/dature/actions/workflows/ci.yml/badge.svg)](https://github.com/reagento/dature/actions/workflows/ci.yml)
[![CodeQL](https://github.com/reagento/dature/actions/workflows/scorecard.yml/badge.svg)](https://github.com/reagento/dature/actions/workflows/scorecard.yml)
[![Dependency Review](https://github.com/reagento/dature/actions/workflows/dependency-review.yml/badge.svg)](https://github.com/reagento/dature/actions/workflows/dependency-review.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Niccolum/57394cf935e48a8a746787f16a1791fc/raw/coverage.json)](https://github.com/reagento/dature/actions/workflows/ci.yml)
\
[![Monthly downloads](https://static.pepy.tech/badge/dature/month)](https://pypi.org/project/dature/)
[![Commits since latest release](https://img.shields.io/github/commits-since/reagento/dature/latest?logo=github)](https://github.com/reagento/dature/commits)
[![Last commit date](https://img.shields.io/github/last-commit/reagento/dature?logo=github&label=Last%20Commit)](https://github.com/reagento/dature/commits)
[![Last release date](https://img.shields.io/github/release-date/reagento/dature?logo=github&label=Release%20Date)](https://github.com/reagento/dature/releases)

</div>

**[Documentation](https://dature.readthedocs.io/)** | **[Changelog](https://dature.readthedocs.io/en/latest/changelog/)**

Type-safe configuration loader for Python dataclasses. Load config from YAML, JSON, TOML, INI, ENV files, environment variables, Docker secrets, CLI arguments, HashiCorp Vault, Consul, etcd, Apache ZooKeeper, AWS SSM, AWS Secrets Manager, Azure App Configuration, Azure Key Vault, and GCP Secret Manager — with automatic type conversion, validation, and human-readable error messages.

## Installation

```bash
pip install dature
```

With optional format support:

```bash
pip install dature[yaml]       # YAML (ruamel.yaml)
pip install dature[json5]      # JSON5
pip install dature[toml]       # TOML (toml_rs)
pip install dature[vault]      # HashiCorp Vault (hvac)
pip install dature[consul]     # Consul (py-consul)
pip install dature[etcd]       # etcd (etcd3gw)
pip install dature[zookeeper]  # Apache ZooKeeper (kazoo)
pip install dature[aws]        # AWS SSM & Secrets Manager (boto3)
pip install dature[azure-appconfig] # Azure App Configuration
pip install dature[azure-keyvault]  # Azure Key Vault
pip install dature[gcp]        # GCP Secret Manager
pip install dature[watch]      # File watching for background reload (watchdog)
pip install dature[secure]     # Secret detection heuristics
pip install dature[type-stubs] # Type stubs for the integrations above (mypy/pyright users)
```

## Quick Start

```python
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = dature.load(dature.Yaml12Source(file="config.yaml"), schema=Config)
```

## Readable errors

Validation errors point at the source file, the line, and the exact value:

```python
from dataclasses import dataclass
from typing import Literal

import dature


@dataclass
class Config:
    password: str
    host: Literal["production", "staging"]


dature.load(
    dature.Yaml12Source(file="config.yaml"),
    schema=Config,
    masking_mode="secrets_only",  # default is "all"
)
```

```yaml title="config.yaml"
host: "development"
password: "my_secret_password"
```

```
  | dature.errors.exceptions.DatureConfigError: Config loading errors (1)
  +-+---------------- 1 ----------------
    | dature.errors.exceptions.FieldLoadError:   [host]  Invalid variant: 'development'
    |    ├── host: "development"
    |    │          ^^^^^^^^^^^
    |    └── FILE 'config.yaml', line 1
    +------------------------------------
```

The same format works for YAML, JSON, JSON5, TOML, INI, ENV files, environment variables, and Docker
secrets. Values are masked by default (`masking_mode="all"`); the example uses `"secrets_only"` so
that only `password` is hidden. See
[Masking](https://dature.readthedocs.io/en/latest/basic/masking/).

## Merging sources

Sources are merged in order, with a strategy for conflicts and per-field rules for lists:

```python
from dataclasses import dataclass

import dature


@dataclass
class Config:
    tags: list[str]


config = dature.load(
    dature.Yaml12Source(file="base.yaml"),  # tags: [web, default]
    dature.Yaml12Source(file="override.yaml"),  # tags: [web, api]
    schema=Config,
    field_merges={dature.F[Config].tags: "append"},
)

print(config.tags)  # ['web', 'default', 'web', 'api']
```

## Debug report

Pass `debug=True` to see which source provided each value:

```python
import dature

config = dature.load(
    dature.Yaml12Source(file="defaults.yaml"),
    dature.Yaml12Source(file="overrides.yaml"),
    schema=Config,
    debug=True,
)

report = dature.load_report(config)
for origin in report.field_origins:
    source = Path(origin.source_file).name if origin.source_file else origin.source_loader_type
    print(f"{origin.key} = {origin.value!r} <- {source}")
```

```
host = 'production.example.com' <- overrides.yaml
port = 3000 <- defaults.yaml
tags = ['default'] <- defaults.yaml
```


## Key Features

- **Multiple sources** — YAML, JSON, JSON5, TOML, INI, ENV, environment variables, Docker secrets, CLI args (`argparse` or your own), HashiCorp Vault, Consul, etcd, Apache ZooKeeper, AWS SSM, AWS Secrets Manager, Azure App Configuration, Azure Key Vault, GCP Secret Manager
- **Merging** — combine multiple sources with configurable strategies (`"last_wins"`, `"first_wins"`, `"first_found"`, `"raise_on_conflict"`) and per-field rules (`"append"`, `"prepend"`, `"append_unique"`, custom callables)
- **Validation** — `Annotated` field validators, root validators, `__post_init__` support
- **Naming** — automatic field name mapping (`snake_case` ↔ `camelCase` ↔ `UPPER_SNAKE` etc.)
- **Secret masking** — automatic masking in error messages and logs by field type, name, or heuristic
- **ENV expansion** — `$VAR`, `${VAR:-default}` substitution in all file formats
- **Special types** — `SecretStr`, `ByteSize`, `PaymentCardNumber`, `URL`, `Base64UrlStr`
- **Debug report** — `debug=True` shows which source provided each field value
- **Decorator mode** — `@dature.load(meta)` auto-loads config on dataclass instantiation with caching
- **Shared reads** — `Source(shared_read=...)` shares one raw file read / remote fetch across multiple `prefix=`-bound schemas
- **CLI** — `dature validate` and `dature inspect` console commands for CI and debugging
- **Cross-source refs & conditional sources** — reference values across sources, activate sources based on environment
- **Extensible** — plug in custom sources, type loaders, and remote backends via `SourceProtocol`

See the **[documentation](https://dature.readthedocs.io/)** for detailed guides and API reference.

## Why dature?

- **Your config stays a plain dataclass.** No `BaseSettings` base class, no vendor lock-in, no Pydantic-specific validators for custom types. Full IDE completion and mypy support come from your own class.
- **Errors you can act on.** The failure names the source, the line, and the value — not a `ValidationError` with a model path.
- **Merge is explicit.** Four source strategies plus per-field rules (`append`, `prepend`, `append_unique`, field groups), instead of a fixed priority order you have to work around.
- **One schema, many backends.** The same dataclass loads from files, environment, CLI, Docker secrets, and remote stores (Vault, Consul, etcd, ZooKeeper, AWS, Azure, GCP) — switch sources without touching the schema.

How dature compares in detail:

- [Why not pydantic-settings?](https://dature.readthedocs.io/en/latest/comparison/why-not-pydantic-settings/)
- [Why not Dynaconf?](https://dature.readthedocs.io/en/latest/comparison/why-not-dynaconf/)
- [Why not Hydra?](https://dature.readthedocs.io/en/latest/comparison/why-not-hydra/)
- [Benchmarks](https://dature.readthedocs.io/en/latest/comparison/benchmarks/)

When the other side wins: if Pydantic is already your core dependency, you build on FastAPI/SQLModel,
or you want a CLI generated from your settings model with subcommands and async entrypoints —
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) is the natural fit.
For ML experiment sweeps and config composition use [Hydra](https://hydra.cc/). dature is aimed at
application and service config: a fixed schema, several sources, and readable failures.

## Requirements

- Python >= 3.12
- [adaptix](https://github.com/reagento/adaptix) >= 3.0.0b11

## Development

```bash
git clone https://github.com/reagento/dature.git
cd dature
uv sync --all-extras --all-groups
```

Run tests:

```bash
uv run pytest tests/ -v
```

Lint and type check:

```bash
uv run prek run --all-files
```

Build docs locally:

```bash
uv run mkdocs serve
```

## Changelog

Each PR must include a [towncrier](https://towncrier.readthedocs.io/) fragment in the `changes/` directory:

```bash
# Format: changes/<issue-or-pr-number>.<type>
echo "Added support for YAML anchors." > changes/42.feature

```

Available `<type>` values:

| Type | Description |
|------|-------------|
| `feature` | New features |
| `bugfix` | Bug fixes |
| `doc` | Documentation improvements |
| `removal` | Deprecations and removals |
| `misc` | Other changes |

Use `+<description>` instead of an issue number for changes without a linked issue:

```bash
echo "Fixed typo in error message." > changes/+fix-typo.bugfix.md
```

## Releasing

1. Run the [Release workflow](https://github.com/reagento/dature/actions/workflows/release.yml) and choose bump type (`patch` / `minor` / `major`). The next version is calculated from the latest git tag automatically.
2. The workflow builds the changelog from fragments and creates a PR.
3. Merge the PR — CI automatically creates the tag, publishes to PyPI, creates a GitHub Release, and updates docs.

## License

Apache License 2.0
