# Why Not Dynaconf?

[Dynaconf](https://www.dynaconf.com/) is a flexible configuration management library with multi-format support, layered environments, and dynamic reloading. It covers a lot of ground.

The problem is **how** it covers it: dynamic attribute access, no schema in code, and validation bolted on as a separate system. dature gives you the same multi-source power with type safety baked in from the start.

## Side-by-Side

| | Dynaconf | dature |
|---|---|---|
| **Config definition** | No schema — `settings.FOO` dynamic access | stdlib `@dataclass` with type hints |
| **Type safety** | Runtime casting, opt-in validation | Enforced by type hints + automatic coercion |
| **IDE support** | Weak — dynamic attributes, no autocompletion | Full — typed dataclass fields |
| **Static analysis (mypy)** | No | Full support, including mypy plugin for decorator mode |
| **Validation** | Separate `Validator` objects | `Annotated` validators inline with field types, root validators, custom validators |
| **Formats** | YAML, TOML, JSON, INI, `.env`, Python files | YAML (1.1/1.2), JSON, JSON5, TOML (1.0/1.1), INI, `.env`, env vars, Docker secrets |
| **Docker secrets** | No built-in | Built-in `DockerSecretsLoader` |
| **Merging** | Layered override + `dynaconf_merge` | 4 strategies + per-field rules (`APPEND`, `PREPEND`, field groups, etc.) |
| **Error messages** | Generic exceptions | Source file, line number, context snippet |
| **Secret masking** | No built-in | Auto-masks secrets in errors and logs |
| **Debug / audit** | No | `debug=True` — which source provided each value |
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
from dature import load, LoadMetadata

@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = load(LoadMetadata(file_="config.toml"), Config)
# config.hostt → AttributeError immediately
# config.port is always int — guaranteed
```

Missing fields, wrong types, invalid values — all caught at load time with clear error messages pointing to the exact source file and line.

## Validation: Inline vs. Afterthought

Dynaconf's validation is a separate system, disconnected from the settings definition:

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

Field definition is in the TOML file, validation rules are in Python, and they reference fields by string name. Nothing connects them — add a new field and forget a validator, and you have no safety.

dature keeps validation **with the type**:

```python
from dataclasses import dataclass
from typing import Annotated
from dature import load, LoadMetadata
from dature.validators import Gt, Lt

@dataclass
class Config:
    host: str
    port: Annotated[int, Gt(0), Lt(65536)]
    debug: bool = False

config = load(LoadMetadata(file_="config.toml"), Config)
```

The type, the constraints, and the default are all in one place. Add a field — the type hint **is** the validation.

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
from dature import load, MergeMetadata, LoadMetadata

config = load(
    MergeMetadata(
        LoadMetadata(file_="defaults.yaml"),
        LoadMetadata(file_="local.yaml", skip_if_broken=True),
        strategy="LAST_WINS",  # or FIRST_WINS, FIRST_FOUND, RAISE_ON_CONFLICT
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

dature:

```
Config loading errors (1)

  [port]  Must be greater than 0
   └── FILE 'config.toml', line 3
       port = 0
```

Source file, line number, the actual config line. No guessing.

## When to Use Dynaconf

Dynaconf is a reasonable choice if:

- You prefer dynamic settings access without defining a schema
- You need per-environment files (`settings.development.toml`, `settings.production.toml`) as a first-class concept
- You want Python files as a config format
- You don't need static analysis or IDE autocompletion for config fields

For **type-safe, schema-first configuration** — dature.
