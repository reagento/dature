Show the dature architecture reference.

Print the following:

---

## Module map

| Module | Role |
|---|---|
| `main.py` | `load()` entry point — dispatches single/multi, function/decorator mode |
| `sources/` | `Source`, `FileSource`, `FlatKeySource` ABC + concrete source classes |
| `loaders/` | Raw value coercion: string → typed Python (bool, float, date, …) |
| `path_finders/` | Line-number lookup inside files for precise error locations |
| `loading/` | Retort building, multi-source orchestration, merge pipeline |
| `merging/` | Merge strategies, field groups, deep dict merge |
| `errors/` | Exception formatting: field path + source location + masked values |
| `expansion/` | `$VAR` / `${VAR:-default}` substitution in all formats |
| `masking/` | Secret masking by type, name heuristic, or explicit list |
| `validators/` | `Annotated` field validators, root validators |
| `fields/` | Special types: `SecretStr`, `ByteSize`, `PaymentCardNumber`, `URL` |
| `config.py` | Global `configure()` / `_ConfigProxy` singleton |
| `protocols.py` | `DataclassInstance` protocol |
| `types.py` | Shared type aliases (`JSONValue`, `FieldMergeMap`, …) |

## Source class hierarchy

```
Source (abc)                        — base: prefix, name_style, validators, masking
├── FileSource (abc)                — adds file=, uses PathFinder for line locations
│   ├── Yaml11Source / Yaml12Source
│   ├── JsonSource / Json5Source
│   ├── Toml10Source / Toml11Source
│   ├── IniSource
│   └── DockerSecretsSource
└── FlatKeySource (abc)             — flat key=value, splits on split_symbols (default __)
    ├── EnvSource                   — reads os.environ
    └── EnvFileSource               — parses .env files
```

## Public API (`src/dature/__init__.py`)

`load`, `configure`, `get_load_report`, `F`, `Source`, `FileSource`,
`EnvSource`, `EnvFileSource`, `JsonSource`, `Json5Source`,
`Yaml11Source`, `Yaml12Source`, `Toml10Source`, `Toml11Source`,
`IniSource`, `DockerSecretsSource`

## Test conventions

- Data files: `tests/fixtures/` (synthetic) or `examples/sources/` (realistic all-types)
- Shared fixtures: `tests/conftest.py`
- `block_import` — simulate missing optional dep
- `_reset_config` — reset global `configure()` state
- `collect_validation_errors` — flatten nested `ValidationLoadError`s
- Module naming: trailing underscore to avoid shadowing stdlib (`yaml_.py`, `json5_.py`)
