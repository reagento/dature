# Basic

Core concepts for everyday dature usage. Start here after the Getting Started guide.

## Topics

| Page | What you'll learn |
|------|-------------------|
| [Naming](naming.md) | Map dataclass field names to config keys: `name_style`, `field_mapping`, `prefix` |
| [Field Paths](field-paths.md) | The `F[Config].field` syntax used across naming, validation, and merge configuration |
| [Validation](validation.md) | `Annotated` validators, root validators, custom validators, `__post_init__` |
| [Merging](merging.md) | Load from multiple sources and combine them with a merge strategy |
| [Masking](masking.md) | Automatic secret detection and masking in logs and reports |
| [Configure](configure.md) | Global defaults via `dature.configure()` |
| [CLI](cli.md) | The `dature inspect` / `dature validate` command-line tool |

## Recommended reading order

1. **Naming** — most configs need at least `name_style`
2. **Merging** — essential once you have more than one source
3. **Validation** — add constraints to keep bad values out
4. **Field Paths** — reference when you see `F[...]` in examples
5. The rest in any order as needed
