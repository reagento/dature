# API Reference

## Core

### `dature.load()`

```python
--8<-- "src/dature/main.py:load"
```

Main entry point. Two calling patterns:

**Function mode** — pass `dataclass_`, get an instance back:

```python
--8<-- "examples/docs/api_reference/api_reference_function_mode.py"
```

**Decorator mode** — omit `dataclass_`, get a decorator:

```python
--8<-- "examples/docs/api_reference/api_reference_decorator_mode.py"
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `*sources` | `Source` | One or more source descriptors. No sources → `Source()` (env vars). Multiple sources → merge mode. |
| `dataclass_` | `type[T] \| None` | Target dataclass. If provided → function mode. If `None` → decorator mode. |
| `cache` | `bool \| None` | Enable caching in decorator mode. Default from `configure()`. |
| `debug` | `bool \| None` | Collect `LoadReport`. Default from `configure()`. |
| `strategy` | `MergeStrategy` | Merge strategy (default `LAST_WINS`). Only used with multiple sources. |
| `field_merges` | `tuple[MergeRule, ...]` | Per-field merge strategy overrides. |
| `field_groups` | `tuple[FieldGroup, ...]` | Groups of fields that must change together. |
| `skip_broken_sources` | `bool` | Skip sources that fail to load (default `False`). |
| `skip_invalid_fields` | `bool` | Skip fields that fail validation (default `False`). |
| `expand_env_vars` | `ExpandEnvVarsMode` | Env var expansion mode for all sources (default `"default"`). |
| `secret_field_names` | `tuple[str, ...] \| None` | Extra secret field name patterns. |
| `mask_secrets` | `bool \| None` | Enable/disable secret masking globally. |
| `type_loaders` | `tuple[TypeLoader, ...] \| None` | Custom type loaders. |
| `nested_resolve_strategy` | `NestedResolveStrategy \| None` | Default priority for JSON vs flat keys. See [Nested Resolve](advanced/nested-resolve.md). |
| `nested_resolve` | `NestedResolve \| None` | Per-field nested resolve strategy overrides. See [Nested Resolve](advanced/nested-resolve.md#per-field-strategy). |

---

### `Source`

```python
--8<-- "src/dature/metadata.py:load-metadata"
```

See [Introduction — Source Reference](introduction.md#source-reference) for parameter descriptions.

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

Usage: `dature.FieldGroup(dature.F[Config].host, dature.F[Config].port)`

---

## Field Path

### `F`

Factory for building field paths with validation:

```python
--8<-- "examples/docs/api_reference/api_reference_field_path.py"
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
