# Why Not pydantic-settings?

pydantic-settings is a mature, well-maintained library backed by the Pydantic ecosystem. It has built-in CLI support, JSON/YAML/TOML file sources, and strong validation via Pydantic's Rust core.

The trade-off is coupling: your config must be a Pydantic model, custom types need Pydantic-specific schemas, and advanced merging or format handling requires writing custom `SettingsSource` classes. dature takes a different approach — stdlib dataclasses, 8 formats out of the box, and explicit merge control.

## Side-by-Side

| | pydantic-settings | dature |
|---|---|---|
| **Base class** | `BaseSettings` (Pydantic model) | stdlib `@dataclass` |
| **Formats** | `.env`, env vars, JSON, YAML, TOML + custom sources | YAML (1.1/1.2), JSON, JSON5, TOML (1.0/1.1), INI, `.env`, env vars, Docker secrets — auto-detected |
| **Merging** | Fixed priority order (init > env > dotenv > secrets > defaults) | 4 strategies + per-field rules (`APPEND`, `PREPEND`, field groups, etc.) |
| **Skip broken sources** | No | Yes — `skip_if_broken`, `skip_if_invalid` |
| **Field groups** | No | Yes — enforce related fields are overridden together |
| **Naming conventions** | `alias` / `alias_generator` (`to_camel`, `to_pascal`, `to_snake`) | Built-in `name_style` (6 conventions) + explicit `field_mapping` with multiple aliases |
| **CLI** | Built-in `CliSettingsSource` with subcommands, async support | No CLI |
| **Secrets** | `SecretStr`, `secrets_dir`, nested secrets directories | `SecretStr`, auto-masking in errors/logs (by type, name pattern, or heuristic) |
| **ENV expansion** | No | `${VAR:-default}` syntax in all file formats |
| **Error messages** | Pydantic `ValidationError` | Human-readable: source file, line number, context snippet |
| **Debug / audit** | No | `debug=True` — which source provided each value |
| **Validation** | Pydantic `field_validator`, `model_validator` (pre/post), constraints | `Annotated` validators, root validators, custom validators, `__post_init__` |
| **Ecosystem** | FastAPI, SQLModel, LangChain integration | Framework-agnostic |
| **Dependency** | pydantic (Rust core) | adaptix + stdlib dataclasses |

## dataclasses, Not Pydantic Models

pydantic-settings requires your config to inherit from `BaseSettings`, which is a Pydantic model. This means:

- **Every instantiation runs full Pydantic validation** — even inside your own code where the data is already valid. This is 3-4x slower than a plain dataclass.
- **Your config is coupled to Pydantic's type system** — custom types need Pydantic-specific validators, serializers, and `__get_pydantic_core_schema__`.
- **Inheritance gets complex** — mixing `BaseSettings` with other classes can cause metaclass conflicts.

dature uses **stdlib `@dataclass`** — no vendor lock-in, no magic metaclasses, no performance overhead on instantiation. Your config classes are plain Python that works with any library.

```python
from dataclasses import dataclass
from dature import load, Source

@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

config = load(Source(file_="config.yaml"), Config)
```

## Multi-Source Merging That Actually Works

pydantic-settings merges sources by simple priority: env vars override `.env` file, which overrides defaults. That's it.

dature gives you **real merge control**:

```python
from dature import load, Merge, Source

config = load(
    Merge(
        Source(file_="defaults.yaml"),
        Source(file_="local.yaml", skip_if_broken=True),
        Source(prefix="APP_"),
    ),
    Config,
)
```

- Broken or missing `local.yaml`? Silently skipped.
- Need lists to be appended instead of replaced? Set `merge_strategy` per field.
- Need to enforce that `db_host` and `db_port` are always overridden together? Use field groups.

With pydantic-settings, implementing any of these requires writing custom `SettingsSource` classes.

## Format Support

pydantic-settings v2 added built-in `JsonConfigSettingsSource`, `YamlConfigSettingsSource`, and `TomlConfigSettingsSource`. But each must be explicitly configured and wired into `settings_customise_sources`:

```python
# pydantic-settings
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="config.toml",
    )

    @classmethod
    def settings_customise_sources(cls, settings_cls, **kwargs):
        return (
            kwargs["init_settings"],
            kwargs["env_settings"],
            TomlConfigSettingsSource(settings_cls),
        )
```

dature **auto-detects** the format from the file extension — no boilerplate:

```python
# Just change the file — dature picks the right loader
Source(file_="config.yaml")
Source(file_="config.toml")
Source(file_="config.json5")
```

dature also supports INI, JSON5, and YAML 1.1/1.2 + TOML 1.0/1.1 version variants — formats that pydantic-settings doesn't cover.

Need a custom format? Subclass `BaseLoader` — one method to implement, not an entire `SettingsSource`.

## Error Messages You Can Actually Read

pydantic-settings gives you a Pydantic `ValidationError` — a wall of JSON-like text with type names and location tuples:

```
validation error for Settings
port
  Input should be a valid integer, unable to parse string as an integer
    [type=int_parsing, input_value='abc', input_type=str]
```

dature tells you **where** the problem is and underlines the exact value:

```
Config loading errors (1)

  [port]  Bad string format
   ├── port: "abc"
   │         ^^^
   └── FILE 'config.yaml', line 2
```

Source file, line number, the actual config line, and caret underline pointing at the problematic value. No guessing.

## What's Coming

dature's architecture is built for extensibility:

- **Remote sources** — Vault, AWS SSM, Consul
- **Built-in caching** — avoid redundant reads on hot paths
- **Config watching** — reload on file changes

These features are possible because dature's loader system is modular by design — not bolted onto a validation framework.

## What pydantic-settings Does Better

To be fair — pydantic-settings has mature features that dature doesn't:

- **CLI support** — built-in `CliSettingsSource` with subcommands, argument parsing, and async CLI commands. dature has no CLI.
- **Pydantic ecosystem** — seamless integration with FastAPI, SQLModel, LangChain. If you're already in this ecosystem, pydantic-settings is the natural fit.
- **Validation power** — Pydantic's `field_validator` and `model_validator` with `mode="before"` / `mode="after"`, computed fields, and the full Pydantic constraint system are more feature-rich than dature's validators.
- **`pyproject.toml` source** — built-in `PyprojectTomlConfigSettingsSource` reads settings directly from `pyproject.toml`.
- **Nested secrets directories** — `NestedSecretsSettingsSource` maps directory structure to nested model fields.
- **Active ecosystem** — large community, frequent releases, extensive third-party documentation.

## When to Use pydantic-settings

pydantic-settings is a reasonable choice if:

- Pydantic is already your core dependency
- You need CLI argument parsing for your settings
- You're building on FastAPI/SQLModel and want tight integration
- You rely on Pydantic's advanced validator features (computed fields, `mode="before"`)
- The fixed priority merge order (init > env > dotenv > secrets) is sufficient

For **multi-source merging, format variety, human-readable errors, and stdlib dataclasses** — dature.
