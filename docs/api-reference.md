# API Reference

## Core

### `load()`

```python
--8<-- "src/dature/main.py:load"
```

Main entry point. Two calling patterns:

**Function mode** — pass `dataclass_`, get an instance back:

```python
config = load(Source(file="config.yaml"), Config)
```

**Decorator mode** — omit `dataclass_`, get a decorator:

```python
@load(Source(file="config.yaml"))
@dataclass
class Config:
    host: str
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `metadata` | `Source \| Merge \| tuple[Source, ...] \| None` | Source descriptor. Tuple is shorthand for `Merge(...)` with `LAST_WINS`. `None` → `Source()` (env vars). |
| `dataclass_` | `type[T] \| None` | Target dataclass. If provided → function mode. If `None` → decorator mode. |
| `cache` | `bool \| None` | Enable caching in decorator mode. Default from `configure()`. |
| `debug` | `bool \| None` | Collect `LoadReport`. Default from `configure()`. |

---

### `Source`

```python
--8<-- "src/dature/metadata.py:load-metadata"
```

See [Introduction — Source Reference](introduction.md#source-reference) for parameter descriptions.

---

### `Merge`

```python
--8<-- "src/dature/metadata.py:merge-metadata"
```

| Parameter | Description |
|-----------|-------------|
| `sources` | Ordered tuple of `Source` to merge |
| `strategy` | Global merge strategy |
| `field_merges` | Per-field strategy overrides |
| `field_groups` | Groups of fields that must change together |
| `skip_broken_sources` | Global default for broken source handling |
| `skip_invalid_fields` | Global default for invalid field handling |
| `expand_env_vars` | Default env expansion mode for all sources |
| `secret_field_names` | Extra secret patterns for all sources |
| `mask_secrets` | Enable/disable masking globally |
| `nested_resolve_strategy` | Default priority for JSON vs flat keys across all sources. See [Nested Resolve](advanced/nested-resolve.md) |
| `nested_resolve` | Default per-field strategy overrides for all sources. See [Nested Resolve](advanced/nested-resolve.md#per-field-strategy) |

---

### `MergeStrategy`

```python
--8<-- "src/dature/metadata.py:merge-strategy"
```

---

### `FieldMergeStrategy`

```python
--8<-- "src/dature/metadata.py:field-merge-strategy"
```

---

### `MergeRule`

```python
--8<-- "src/dature/metadata.py:merge-rule"
```

---

### `FieldGroup`

```python
--8<-- "src/dature/metadata.py:field-group"
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
--8<-- "src/dature/load_report.py:get-load-report"
```

Returns the `LoadReport` attached to a loaded instance (or type on error). Returns `None` and emits a warning if `debug=True` was not passed.

### `LoadReport`, `SourceEntry`, `FieldOrigin`

```python
--8<-- "src/dature/load_report.py:report-structure"
```

---

## Configuration

### `configure()`

```python
--8<-- "src/dature/config.py:configure"
```

Set global configuration. `None` parameters keep their current values.

### `MaskingConfig`

```python
--8<-- "src/dature/config.py:masking-config"
```

### `ErrorDisplayConfig`

```python
--8<-- "src/dature/config.py:error-display-config"
```

### `LoadingConfig`

```python
--8<-- "src/dature/config.py:loading-config"
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
--8<-- "src/dature/validators/root.py:root-validator"
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
