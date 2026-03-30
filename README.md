# dature

---

<div align="center">

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

import dature

@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = dature.load(dature.Source(file="config.yaml"), Config)
```

## Key Features

- **Multiple formats** — YAML, JSON, JSON5, TOML, INI, ENV, environment variables, Docker secrets
- **Merging** — combine multiple sources with configurable strategies (`"last_wins"`, `"first_wins"`, `"raise_on_conflict"`)
- **Validation** — `Annotated` field validators, root validators, `__post_init__` support
- **Naming** — automatic field name mapping (`snake_case` ↔ `camelCase` ↔ `UPPER_SNAKE` etc.)
- **Secret masking** — automatic masking in error messages and logs by field type, name, or heuristic
- **ENV expansion** — `$VAR`, `${VAR:-default}` substitution in all file formats
- **Special types** — `SecretStr`, `ByteSize`, `PaymentCardNumber`, `URL`, `Base64UrlStr`
- **Debug report** — `debug=True` shows which source provided each field value
- **Decorator mode** — `@dature.load(meta)` auto-loads config on dataclass instantiation with caching

See the **[documentation](https://dature.readthedocs.io/)** for detailed guides and API reference.

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
