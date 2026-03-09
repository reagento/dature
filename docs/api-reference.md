# API Reference

## Core

### `load()`

```python
def load(
    metadata: LoadMetadata | MergeMetadata | tuple[LoadMetadata, ...] | None = None,
    /,
    dataclass_: type[T] | None = None,
    *,
    cache: bool | None = None,
    debug: bool | None = None,
) -> T | Callable[[type], type]
```

Main entry point. Two calling patterns:

**Function mode** — pass `dataclass_`, get an instance back:

```python
config = load(LoadMetadata(file_="config.yaml"), Config)
```

**Decorator mode** — omit `dataclass_`, get a decorator:

```python
@load(LoadMetadata(file_="config.yaml"))
@dataclass
class Config:
    host: str
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `metadata` | `LoadMetadata \| MergeMetadata \| tuple[LoadMetadata, ...] \| None` | Source descriptor. Tuple is shorthand for `MergeMetadata(sources=...)` with `LAST_WINS`. `None` → `LoadMetadata()` (env vars). |
| `dataclass_` | `type[T] \| None` | Target dataclass. If provided → function mode. If `None` → decorator mode. |
| `cache` | `bool \| None` | Enable caching in decorator mode. Default from `configure()`. |
| `debug` | `bool \| None` | Collect `LoadReport`. Default from `configure()`. |

---

### `LoadMetadata`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LoadMetadata:
    file_: FileLike | FilePath | None = None  # str, Path, or file-like object
    loader: type[LoaderProtocol] | None = None
    prefix: DotSeparatedPath | None = None
    split_symbols: str = "__"
    name_style: NameStyle | None = None
    field_mapping: FieldMapping | None = None
    root_validators: tuple[ValidatorProtocol, ...] | None = None
    validators: FieldValidators | None = None
    expand_env_vars: ExpandEnvVarsMode | None = None
    skip_if_broken: bool | None = None
    skip_if_invalid: bool | tuple[FieldPath, ...] | None = None
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
```

See [Introduction — LoadMetadata Reference](introduction.md#loadmetadata-reference) for parameter descriptions.

---

### `MergeMetadata`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class MergeMetadata:
    sources: tuple[LoadMetadata, ...]
    strategy: MergeStrategy = MergeStrategy.LAST_WINS
    field_merges: tuple[MergeRule, ...] = ()
    field_groups: tuple[FieldGroup, ...] = ()
    skip_broken_sources: bool = False
    skip_invalid_fields: bool = False
    expand_env_vars: ExpandEnvVarsMode = "default"
    secret_field_names: tuple[str, ...] | None = None
    mask_secrets: bool | None = None
```

| Parameter | Description |
|-----------|-------------|
| `sources` | Ordered tuple of `LoadMetadata` to merge |
| `strategy` | Global merge strategy |
| `field_merges` | Per-field strategy overrides |
| `field_groups` | Groups of fields that must change together |
| `skip_broken_sources` | Global default for broken source handling |
| `skip_invalid_fields` | Global default for invalid field handling |
| `expand_env_vars` | Default env expansion mode for all sources |
| `secret_field_names` | Extra secret patterns for all sources |
| `mask_secrets` | Enable/disable masking globally |

---

### `MergeStrategy`

```python
class MergeStrategy(StrEnum):
    LAST_WINS = "last_wins"
    FIRST_WINS = "first_wins"
    RAISE_ON_CONFLICT = "raise_on_conflict"
```

---

### `FieldMergeStrategy`

```python
class FieldMergeStrategy(StrEnum):
    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"
    APPEND = "append"
    APPEND_UNIQUE = "append_unique"
    PREPEND = "prepend"
    PREPEND_UNIQUE = "prepend_unique"
```

---

### `MergeRule`

```python
@dataclass(frozen=True, slots=True)
class MergeRule:
    predicate: FieldPath
    strategy: FieldMergeStrategy | FieldMergeCallable
```

---

### `FieldGroup`

```python
@dataclass(frozen=True, slots=True)
class FieldGroup:
    fields: tuple[FieldPath, ...]

    def __init__(self, *fields: FieldPath) -> None: ...
```

Usage: `FieldGroup(F[Config].host, F[Config].port)`

---

## Field Path

### `F`

Factory for building field paths with validation:

```python
F[Config].host           # FieldPath with eager validation
F[Config].database.host  # nested path
F["Config"].host         # string-based, no validation (for decorator mode)
```

---

## Report

### `get_load_report()`

```python
def get_load_report(instance: Any) -> LoadReport | None
```

Returns the `LoadReport` attached to a loaded instance (or type on error). Returns `None` and emits a warning if `debug=True` was not passed.

### `LoadReport`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LoadReport:
    dataclass_name: str
    strategy: MergeStrategy | None
    sources: tuple[SourceEntry, ...]
    field_origins: tuple[FieldOrigin, ...]
    merged_data: JSONValue
```

### `SourceEntry`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class SourceEntry:
    index: int
    file_path: str | None
    loader_type: str
    raw_data: JSONValue
```

### `FieldOrigin`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FieldOrigin:
    key: str
    value: JSONValue
    source_index: int
    source_file: str | None
    source_loader_type: str
```

---

## Configuration

### `configure()`

```python
def configure(
    *,
    masking: MaskingConfig | None = None,
    error_display: ErrorDisplayConfig | None = None,
    loading: LoadingConfig | None = None,
) -> None
```

Set global configuration. `None` parameters keep their current values.

### `MaskingConfig`

```python
@dataclass(frozen=True, slots=True)
class MaskingConfig:
    mask_char: str = "*"
    min_visible_chars: int = 2
    min_length_for_partial_mask: int = 5
    fixed_mask_length: int = 5
    min_heuristic_length: int = 8
    secret_field_names: tuple[str, ...] = (...)
    mask_secrets: bool = True
```

### `ErrorDisplayConfig`

```python
@dataclass(frozen=True, slots=True)
class ErrorDisplayConfig:
    max_visible_lines: int = 3
    max_line_length: int = 80
```

### `LoadingConfig`

```python
@dataclass(frozen=True, slots=True)
class LoadingConfig:
    cache: bool = True
    debug: bool = False
```

---

## Validators

All validators are frozen dataclasses implementing `get_validator_func()` and `get_error_message()`.

### Number Validators (`dature.validators.number`)

| Class | Parameter | Description |
|-------|-----------|-------------|
| `Gt` | `value: int \| float` | Greater than |
| `Ge` | `value: int \| float` | Greater than or equal |
| `Lt` | `value: int \| float` | Less than |
| `Le` | `value: int \| float` | Less than or equal |

### String Validators (`dature.validators.string`)

| Class | Parameter | Description |
|-------|-----------|-------------|
| `MinLength` | `value: int` | Minimum length |
| `MaxLength` | `value: int` | Maximum length |
| `RegexPattern` | `pattern: str` | Regex match |

### Sequence Validators (`dature.validators.sequence`)

| Class | Parameter | Description |
|-------|-----------|-------------|
| `MinItems` | `value: int` | Minimum items |
| `MaxItems` | `value: int` | Maximum items |
| `UniqueItems` | — | All items unique |

### Root Validator (`dature.validators.root`)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class RootValidator:
    func: Callable[[Any], bool]
    error_message: str
```

---

## Special Types

| Type | Module | Description |
|------|--------|-------------|
| `SecretStr` | `dature.fields.secret_str` | Masked string with `get_secret_value()` |
| `ByteSize` | `dature.fields.byte_size` | Human-readable byte sizes |
| `PaymentCardNumber` | `dature.fields.payment_card` | Luhn-validated card with brand detection |
| `URL` | `dature.types` | Alias for `urllib.parse.ParseResult` |
| `Base64UrlStr` | `dature.types` | Base64-decoded string |
| `Base64UrlBytes` | `dature.types` | Base64-decoded bytes |

---

## Loaders

| Loader | Module | Format |
|--------|--------|--------|
| `JsonLoader` | `dature.sources_loader.json_` | JSON |
| `Json5Loader` | `dature.sources_loader.json5_` | JSON5 |
| `Yaml11Loader` | `dature.sources_loader.yaml_` | YAML 1.1 |
| `Yaml12Loader` | `dature.sources_loader.yaml_` | YAML 1.2 |
| `Toml10Loader` | `dature.sources_loader.toml_` | TOML 1.0 |
| `Toml11Loader` | `dature.sources_loader.toml_` | TOML 1.1 |
| `IniLoader` | `dature.sources_loader.ini_` | INI |
| `EnvLoader` | `dature.sources_loader.env_` | Environment variables |
| `EnvFileLoader` | `dature.sources_loader.env_` | .env files |
| `DockerSecretsLoader` | `dature.sources_loader.docker_secrets` | Docker secrets directory |

---

## Exceptions

| Exception | Description |
|-----------|-------------|
| `DatureError` | Base exception |
| `DatureConfigError` | Aggregated config loading errors |
| `MergeConflictError` | Merge conflict between sources |
| `FieldGroupError` | Field group constraint violation |
| `EnvVarExpandError` | Missing environment variables in strict mode |
| `FieldLoadError` | Single field loading error |
| `SourceLoadError` | Source loading failure |

All exceptions are in `dature.errors.exceptions`.

---

## Type Aliases

| Alias | Definition | Module |
|-------|------------|--------|
| `FileLike` | `TextIOBase \| BufferedIOBase \| RawIOBase` | `dature.types` |
| `FilePath` | `str \| Path` | `dature.types` |
| `FileOrStream` | `Path \| FileLike` | `dature.types` |
| `NameStyle` | `Literal["lower_snake", "upper_snake", "lower_camel", "upper_camel", "lower_kebab", "upper_kebab"]` | `dature.types` |
| `ExpandEnvVarsMode` | `Literal["disabled", "default", "empty", "strict"]` | `dature.types` |
| `FieldMapping` | `dict[FieldPath, str \| tuple[str, ...]]` | `dature.types` |
| `FieldValidators` | `dict[FieldPath, ValidatorProtocol \| tuple[ValidatorProtocol, ...]]` | `dature.types` |
| `FieldMergeCallable` | `Callable[[list[JSONValue]], JSONValue]` | `dature.types` |
| `JSONValue` | `dict[str, JSONValue] \| list[JSONValue] \| str \| int \| float \| bool \| None` | `dature.types` |
