# Why Not Dynaconf?

[Dynaconf](https://www.dynaconf.com/) is a flexible configuration management library with multi-format support, layered environments, and dynamic reloading. It covers a lot of ground.

The trade-off is **how** it covers it: Dynaconf is powerful and battle-tested, but it trades type safety for flexibility — dynamic attribute access, no schema in code, and config result that's a dict-like object rather than your dataclass. dature takes a different approach: schema-first, type-safe, with your `@dataclass` as the single source of truth.

## Side-by-Side

| | Dynaconf | dature |
|---|---|---|
| **Config definition** | No schema — `settings.FOO` dynamic access | stdlib `@dataclass` with type hints |
| **Type safety** | Runtime casting, opt-in validation | Enforced by type hints + automatic coercion |
| **IDE support** | Weak — dynamic attributes, no autocompletion | Full — typed dataclass fields |
| **Static analysis (mypy)** | No | Full support, including mypy plugin for decorator mode |
| **Validation** | Separate `Validator` objects | Both: `Annotated` inline validators + separate root/custom validators |
| **Formats** | YAML, TOML, JSON, INI, `.env`, Python files | YAML (1.1/1.2), JSON, JSON5, TOML (1.0/1.1), INI, `.env`, env vars, Docker secrets |
| **Remote sources** | Vault, Redis + community plugins | Not yet (planned) |
| **Merging** | Layered override + `dynaconf_merge` | 4 strategies + per-field rules (`APPEND`, `PREPEND`, field groups, etc.) |
| **Dynamic variables** | `@format`, `@jinja` templates with lazy evaluation | `${VAR:-default}` env expansion in all formats |
| **CLI** | `dynaconf list`, `inspect`, `write`, `validate`, etc. | No CLI |
| **Per-environment files** | Built-in (`[development]`, `[production]` sections) | Manual via multiple `Source` objects |
| **Framework extensions** | Django, Flask built-in | No — framework-agnostic by design |
| **Feature flags** | Built-in simple system | No |
| **Error messages** | Generic exceptions | Source file, line number, context snippet |
| **Secret masking** | No built-in | Auto-masks secrets in errors and logs |
| **Debug / audit** | `inspect_settings`, `get_history` | `debug=True` — which source provided each value |
| **Config result** | `Dynaconf` object (dict-like) | Your actual `@dataclass` instance |

## No Schema, No Safety Net

Dynaconf doesn't require you to define what your configuration looks like:

```python
# Dynaconf
from dynaconf import Dynaconf

settings = Dynaconf(settings_files=["config.toml"])

# Any attribute access "works" — even typos
print(settings.HOST)       # might be str, might be None
print(settings.HOSTT)      # no error, just returns empty
print(settings.PORT + 1)   # might crash at runtime if PORT is str
```

There's no schema in your code that says "these fields exist, with these types." Your IDE can't autocomplete, mypy can't check, and typos silently return empty values.

dature makes your config a **typed dataclass**:

```python
from dataclasses import dataclass
from dature import load, Source

@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = load(Source(file_="config.toml"), Config)
# config.hostt → AttributeError immediately
# config.port is always int — guaranteed
```

Missing fields, wrong types, invalid values — all caught at load time with clear error messages pointing to the exact source file and line.

## Validation: Separate vs. Both

Dynaconf keeps validation separate from settings definition — and that's a valid approach for some teams:

```python
# Dynaconf
from dynaconf import Dynaconf, Validator

settings = Dynaconf(
    settings_files=["config.toml"],
    validators=[
        Validator("PORT", gte=1, lte=65535),
        Validator("HOST", must_exist=True),
        Validator("DEBUG", is_type_of=bool),
    ],
)
settings.validators.validate()
```

This gives flexibility — validators can be defined in a different module, reused, or composed dynamically.

dature supports **both approaches**. Inline validators live with the type:

```python
from dataclasses import dataclass
from typing import Annotated
from dature import load, Source
from dature.validators.number import Gt, Lt

@dataclass
class Config:
    host: str
    port: Annotated[int, Gt(0), Lt(65536)]
    debug: bool = False

config = load(Source(file_="config.toml"), Config)
```

And separate validators when you need cross-field checks or decoupled validation logic:

```python
from dature import load, Source

def check_debug_port(config: Config) -> None:
    if config.debug and config.port == 80:
        raise ValueError("debug mode should not use port 80")

config = load(
    Source(file_="config.toml", root_validators=[check_debug_port]),
    Config,
)
```

You choose the style that fits — or mix them.

## Merging: Magic Keys vs. Explicit Strategies

Dynaconf merges layers by overriding top-level keys. To merge nested structures instead of replacing them, you use special `dynaconf_merge` keys inside your config files:

```toml
# settings.toml
[databases]
host = "localhost"
port = 5432

# settings.local.toml — this REPLACES databases entirely
[databases]
port = 5433
# databases.host is now gone!

# To merge, you need:
[databases]
dynaconf_merge = true
port = 5433
```

This leaks infrastructure concerns into your config files. Every team member needs to know about `dynaconf_merge`, or they'll accidentally wipe nested sections.

dature uses **explicit strategies in code**:

```python
from dature import load, Merge, Source

config = load(
    Merge(
        sources=(
            Source(file_="defaults.yaml"),
            Source(file_="local.yaml", skip_if_broken=True),
        ),
        strategy="last_wins",  # or first_wins, first_found, raise_on_conflict
    ),
    Config,
)
```

No magic keys in config files. Merge behavior is defined in code, visible in one place.

## Error Messages

Dynaconf:

```
dynaconf.validator.ValidationError: PORT must gte 1 but it is 0 in env main
```

dature points to the exact value:

```
Config loading errors (1)

  [port]  Must be greater than 0
   ├── port = 0
   │          ^
   └── FILE 'config.toml', line 3
```

Source file, line number, the actual config line, and caret underline on the problematic value.

## What Dynaconf Does Better

To be fair — Dynaconf has mature features that dature doesn't (yet):

- **Remote sources** — Vault, Redis integration out of the box. dature plans remote sources (Vault, AWS SSM) but doesn't have them yet.
- **CLI tooling** — `dynaconf list`, `inspect`, `write`, `validate` commands for operational use.
- **Dynamic variables** — `@format` and `@jinja` templates with lazy evaluation and Python expressions. dature supports `${VAR:-default}` env expansion, but not Jinja templates.
- **Per-environment sections** — `[development]`, `[production]` sections in a single file with automatic switching via `ENV_FOR_DYNACONF`.
- **Framework extensions** — built-in Django and Flask integration.
- **Feature flags** — simple built-in feature flag system.
- **Python files as config** — load settings from `.py` files directly.

## When to Use Dynaconf

Dynaconf is a reasonable choice if:

- You need remote config sources (Vault, Redis) today
- You rely on CLI tooling for config inspection and management
- You need per-environment sections in a single file
- You want Jinja templates in config values
- You use Django/Flask and want drop-in config integration
- You prefer dynamic settings access without defining a schema

For **type-safe, schema-first configuration** — dature.
