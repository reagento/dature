# Why Not pydantic-settings?

pydantic-settings is a good choice when Pydantic is already in your project and your configuration is simple: a few environment variables, maybe a `.env` file. For that scenario it works well.

But once your requirements grow — multiple config files, layered overrides, custom formats, secrets management — pydantic-settings starts showing its limits. dature is designed for exactly these cases.

## Side-by-Side

| | pydantic-settings | dature |
|---|---|---|
| **Base class** | `BaseSettings` (Pydantic model) | stdlib `@dataclass` |
| **Formats** | `.env`, env vars; others via custom sources | YAML, JSON, JSON5, TOML, INI, `.env`, env vars, Docker secrets — auto-detected |
| **Merging multiple sources** | Priority order only | 4 strategies (`LAST_WINS`, `FIRST_WINS`, `FIRST_FOUND`, `RAISE_ON_CONFLICT`) + per-field rules (`APPEND`, `PREPEND`, `APPEND_UNIQUE`, etc.) |
| **Skip broken sources** | No | Yes — `skip_if_broken`, `skip_if_invalid` |
| **Field groups** | No | Yes — enforce related fields are overridden together |
| **Naming conventions** | Manual `alias` / `alias_generator` | Built-in `name_style` (`camelCase`, `UPPER_SNAKE`, etc.) + explicit `field_mapping` |
| **Secret masking** | No built-in | Auto-masks secrets in errors and logs (by type, name pattern, or heuristic) |
| **ENV expansion** | No | `${VAR:-default}` syntax in all file formats |
| **Error messages** | Pydantic `ValidationError` | Human-readable: source file, line number, context snippet |
| **Debug / audit** | No | `debug=True` shows which source provided each value |
| **Validation** | Pydantic validators | `Annotated` validators, root validators, custom validators, `__post_init__` |
| **Dependency** | pydantic (Rust core) | adaptix + stdlib dataclasses |

## dataclasses, Not Pydantic Models

pydantic-settings requires your config to inherit from `BaseSettings`, which is a Pydantic model. This means:

- **Every instantiation runs full Pydantic validation** — even inside your own code where the data is already valid. This is 3-4x slower than a plain dataclass.
- **Your config is coupled to Pydantic's type system** — custom types need Pydantic-specific validators, serializers, and `__get_pydantic_core_schema__`.
- **Inheritance gets complex** — mixing `BaseSettings` with other classes can cause metaclass conflicts.

dature uses **stdlib `@dataclass`** — no vendor lock-in, no magic metaclasses, no performance overhead on instantiation. Your config classes are plain Python that works with any library.

```python
from dataclasses import dataclass
from dature import load, LoadMetadata

@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = load(LoadMetadata(file_="config.yaml"), Config)
```

## Multi-Source Merging That Actually Works

pydantic-settings merges sources by simple priority: env vars override `.env` file, which overrides defaults. That's it.

dature gives you **real merge control**:

```python
from dature import load, MergeMetadata, LoadMetadata

config = load(
    MergeMetadata(
        LoadMetadata(file_="defaults.yaml"),
        LoadMetadata(file_="local.yaml", skip_if_broken=True),
        LoadMetadata(prefix="APP_"),
    ),
    Config,
)
```

- Broken or missing `local.yaml`? Silently skipped.
- Need lists to be appended instead of replaced? Set `merge_strategy` per field.
- Need to enforce that `db_host` and `db_port` are always overridden together? Use field groups.

With pydantic-settings, implementing any of these requires writing custom `SettingsSource` classes.

## Formats Beyond `.env`

pydantic-settings is built around environment variables. YAML, TOML, JSON — each needs a [custom source class](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources). You write the file reading, the parsing, and the nested key handling yourself.

dature supports **8 formats out of the box** with auto-detection from file extension:

```python
# Just change the file — dature picks the right loader
LoadMetadata(file_="config.yaml")
LoadMetadata(file_="config.toml")
LoadMetadata(file_="config.json5")
LoadMetadata(file_="/run/secrets/")  # Docker secrets directory
```

Need a custom format? Subclass `BaseLoader` — one method to implement, not an entire `SettingsSource`.

## Error Messages You Can Actually Read

pydantic-settings gives you a Pydantic `ValidationError` — a wall of JSON-like text with type names and location tuples:

```
validation error for Settings
port
  Input should be a valid integer, unable to parse string as an integer
    [type=int_parsing, input_value='abc', input_type=str]
```

dature tells you **where** the problem is:

```
Config loading errors (1)

  [port]  Bad string format
   └── FILE 'config.yaml', line 2
       port: "abc"
```

Source file, line number, the actual line from your config. No guessing.

## What's Coming

dature's architecture is built for extensibility:

- **Remote sources** — Vault, AWS SSM, Consul
- **Built-in caching** — avoid redundant reads on hot paths
- **Config watching** — reload on file changes

These features are possible because dature's loader system is modular by design — not bolted onto a validation framework.

## When to Use pydantic-settings

pydantic-settings is still a reasonable choice if:

- Pydantic is already your core dependency
- You only need env vars and `.env` files
- You don't need multi-source merging or format variety
- Pydantic's error format is acceptable for your use case

For everything else — **dature**.
