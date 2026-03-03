# dature

[![CI](https://github.com/Niccolum/dature/actions/workflows/ci.yml/badge.svg)](https://github.com/Niccolum/dature/actions/workflows/ci.yml)
[![Documentation](https://readthedocs.org/projects/dature/badge/?version=latest)](https://dature.readthedocs.io/)
[![PyPI](https://img.shields.io/pypi/v/dature)](https://pypi.org/project/dature/)
[![Python](https://img.shields.io/pypi/pyversions/dature)](https://pypi.org/project/dature/)

**[Documentation](https://dature.readthedocs.io/)** | **[Changelog](https://dature.readthedocs.io/changelog/)**

Type-safe configuration loader for Python dataclasses. Load config from YAML, JSON, TOML, INI, ENV files, environment variables, and Docker secrets — with automatic type conversion, validation, and human-readable error messages.

## Installation

```bash
pip install dature
```

With optional format support:

```bash
pip install dature[yaml]    # YAML (ruamel.yaml)
pip install dature[json5]   # JSON5
pip install dature[toml]    # TOML (toml_rs)
pip install dature[secure]  # Secret detection heuristics
```

## Quick Start

```python
from dataclasses import dataclass
from dature import LoadMetadata, load

@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = load(LoadMetadata(file_="config.yaml"), Config)
```

## Key Features

- **Multiple formats** — YAML, JSON, JSON5, TOML, INI, ENV, environment variables, Docker secrets
- **Merging** — combine multiple sources with configurable strategies (`LAST_WINS`, `FIRST_WINS`, `RAISE_ON_CONFLICT`)
- **Validation** — `Annotated` field validators, root validators, `__post_init__` support
- **Naming** — automatic field name mapping (`snake_case` ↔ `camelCase` ↔ `UPPER_SNAKE` etc.)
- **Secret masking** — automatic masking in error messages and logs by field type, name, or heuristic
- **ENV expansion** — `$VAR`, `${VAR:-default}` substitution in all file formats
- **Special types** — `SecretStr`, `ByteSize`, `PaymentCardNumber`, `URL`, `Base64UrlStr`
- **Debug report** — `debug=True` shows which source provided each field value
- **Decorator mode** — `@load(meta)` auto-loads config on dataclass instantiation with caching

See the **[documentation](https://dature.readthedocs.io/)** for detailed guides and API reference.

## Requirements

- Python >= 3.12
- [adaptix](https://github.com/reagento/adaptix) >= 3.0.0b11

## Development

```bash
git clone https://github.com/Niccolum/dature.git
cd dature
uv sync --all-extras --dev
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
uv sync --group docs
uv run mkdocs serve
```

## License

Apache License 2.0
