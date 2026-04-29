# API Reference

## Core

### `dature.load()`

```python
--8<-- "src/dature/main.py:load"
```

Main entry point. Two calling patterns:

**Function mode** — pass `schema`, get an instance back:

```python
--8<-- "examples/docs/api_reference/api_reference_function_mode.py"
```

**Decorator mode** — omit `schema`, get a decorator:

```python
--8<-- "examples/docs/api_reference/api_reference_decorator_mode.py"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*sources` | `Source` | — | One or more source descriptors (e.g. `JsonSource(file=...)`, `EnvSource()`). Multiple sources → merge mode. |
| `schema` | `type[T] \| None` | `None` | Target dataclass. If provided → function mode. If `None` → decorator mode. |
| `cache` | `bool \| None` | `None` | Enable caching in decorator mode. Default from `configure()`. Ignored in function mode. |
| `debug` | `bool \| None` | `None` | Collect `LoadReport` on the result instance. Default from `configure()`. Retrieve with `get_load_report()`. |
| `strategy` | `MergeStrategyName \| SourceMergeStrategy` | `"last_wins"` | Merge strategy: a built-in name or a custom object implementing `SourceMergeStrategy`. Only used with multiple sources. See [Merge Strategies](#merge-strategies). |
| `field_merges` | `FieldMergeMap \| None` | `None` | Per-field merge strategy overrides. Maps `F[Config].field` to a strategy name, callable, or any object implementing `FieldMergeStrategy`. See [Field Merge Strategies](#field-merge-strategies). |
| `field_groups` | `tuple[FieldGroupTuple, ...]` | `()` | Groups of fields that must change together. Each group is a tuple of `F[Config].field` references. |
| `skip_broken_sources` | `bool` | `False` | Skip sources that fail to load instead of raising. |
| `skip_invalid_fields` | `bool` | `False` | Skip fields that fail validation instead of raising. |
| `expand_env_vars` | `ExpandEnvVarsMode \| None` | `None` | Env var expansion mode applied to all sources. Source-level setting takes priority. |
| `secret_field_names` | `tuple[str, ...] \| None` | `None` | Extra secret field name patterns for masking. |
| `mask_secrets` | `bool \| None` | `None` | Enable/disable secret masking globally. |
| `type_loaders` | `TypeLoaderMap \| None` | `None` | Custom type loaders mapping types to conversion functions. Merged with source-level and global loaders. |
| `nested_resolve_strategy` | `NestedResolveStrategy \| None` | `None` | Default priority for JSON vs flat keys in `FlatKeySource`. See [Nested Resolve](advanced/nested-resolve.md). |
| `nested_resolve` | `NestedResolve \| None` | `None` | Per-field nested resolve strategy overrides. See [Nested Resolve](advanced/nested-resolve.md#per-field-strategy). |

**Returns:**

- **Function mode** (`schema` provided): an instance of `schema` populated from the sources.
- **Decorator mode** (`schema=None`): a decorator that adds `load()` logic to the decorated dataclass.

**Raises:**

- `TypeError` — no sources passed, or a positional argument is not a `Source` instance.
- `DatureConfigError` — aggregated field loading errors.
- `MergeConflictError` — conflicting values with `strategy="raise_on_conflict"`.
- `FieldGroupError` — field group constraint violation.
- `EnvVarExpandError` — missing env vars with `expand_env_vars="strict"`.

---

### `Source`

```python
--8<-- "src/dature/sources/base.py:load-metadata"
```

Abstract base class for all sources. See [Introduction — Source Reference](introduction.md#source-reference) for parameter descriptions.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prefix` | `DotSeparatedPath \| None` | `None` | Filter ENV keys (`"APP_"`) or extract nested object (`"app.database"`). |
| `name_style` | `NameStyle \| None` | `None` | Naming convention mapping: `"lower_snake"`, `"upper_snake"`, `"lower_camel"`, `"upper_camel"`, `"lower_kebab"`, `"upper_kebab"`. |
| `field_mapping` | `FieldMapping \| None` | `None` | Explicit field renaming with `F` objects. |
| `root_validators` | `tuple[ValidatorProtocol, ...] \| None` | `None` | Post-load validation of the entire object. |
| `validators` | `FieldValidators \| None` | `None` | Per-field validators via `Annotated` metadata or explicit mapping. |
| `expand_env_vars` | `ExpandEnvVarsMode \| None` | `None` | ENV variable expansion: `"disabled"`, `"default"`, `"empty"`, `"strict"`. |
| `skip_if_broken` | `bool \| None` | `None` | Skip this source if it fails to load. |
| `skip_field_if_invalid` | `bool \| tuple[FieldPath, ...] \| None` | `None` | Skip invalid fields from this source. `True` for all, or a tuple of specific fields. |
| `type_loaders` | `TypeLoaderMap \| None` | `None` | Custom type converters `{type: callable}` for this source. |

**Public methods:**

| Method | Return type | Description |
|--------|-------------|-------------|
| `load_raw()` | `LoadRawResult` | Load raw data, apply prefix filtering and env var expansion. Returns `LoadRawResult(data, nested_conflicts)`. |
| `transform_to_dataclass(data, schema)` | `T` | Convert a `JSONValue` dict into a dataclass instance using adaptix. Caches the retort per schema type. |
| `create_retort()` | `Retort` | Build an adaptix `Retort` with base loaders, name mapping, and type loaders. |
| `create_validating_retort(schema)` | `Retort` | Like `create_retort()`, plus field and root validators extracted from `schema`. |
| `create_probe_retort()` | `Retort` | Retort that skips missing fields — used internally for partial loading in merge mode. |
| `file_display()` | `str \| None` | Human-readable file identifier for logging. Returns `None` by default. |
| `file_path_for_errors()` | `Path \| None` | File path used in error messages. Returns `None` by default. |
| `resolve_location(...)` | `list[SourceLocation]` | Locate a field in the source content for error reporting. Returns `SourceLocation` with line range, env var name, etc. |

### `FileSource(Source)`

Base class for file-based sources (`JsonSource`, `Yaml11Source`, `Toml10Source`, `IniSource`, etc.).

```python
--8<-- "src/dature/sources/base.py:file-source"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | `FileLike \| FilePath \| None` | `None` | Path to the config file (`str`, `Path`), or an open file-like object (`StringIO`, `BytesIO`, any `TextIOBase`/`BufferedIOBase`/`RawIOBase`). If `None`, the path defaults to the current directory. |

**Overridden methods:**

| Method | Behavior |
|--------|----------|
| `file_display()` | Returns the path as string, `"<stream>"` for file-like objects, or `None` when `file=None`. |
| `file_path_for_errors()` | Returns `Path` for string/Path inputs, `None` for streams or `None`. |
| `__repr__()` | Returns `"format_name 'file_path'"` or just `"format_name"`. |

### `FlatKeySource(Source)`

Base class for flat key=value sources (`EnvSource`, `EnvFileSource`, `DockerSecretsSource`).

```python
--8<-- "src/dature/sources/base.py:flat-key-source"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `nested_sep` | `str` | `"__"` | Separator for nested key splitting. `APP__DB__HOST` → `{"db": {"host": ...}}` |
| `nested_resolve_strategy` | `NestedResolveStrategy` | `"flat"` | Default priority when both flat and JSON keys exist: `"flat"` or `"json"`. See [Nested Resolve](advanced/nested-resolve.md). |
| `nested_resolve` | `NestedResolve \| None` | `None` | Per-field nested resolve strategy overrides. See [Nested Resolve](advanced/nested-resolve.md#per-field-strategy). |

**Behavior:** All values are strings. Automatic parsing of `str`, `float`, `date`, `datetime`, `time`, `bytearray`, `bool`, `None`, `str | None`. Nested JSON in values (`[...]`, `{...}`) is inferred. `load_raw()` returns `LoadRawResult` with `nested_conflicts` populated when both flat and JSON keys exist for the same field.

---

### Merge Strategies

Strategies for resolving field values across multiple sources. Set via `strategy` parameter of `load()`.

| Strategy | Behavior |
|----------|----------|
| `"last_wins"` | Last source overrides (default). |
| `"first_wins"` | First source wins. |
| `"first_found"` | Uses the first source that loads successfully. |
| `"raise_on_conflict"` | Raises `MergeConflictError` on conflicting values. |

The built-ins are also exposed as classes from `dature.strategies.source` (`SourceLastWins`, `SourceFirstWins`, `SourceFirstFound`, `SourceRaiseOnConflict`) implementing the public `SourceMergeStrategy` `Protocol`. Pass any object satisfying that protocol as `strategy` for custom merge logic — see [Custom Source Strategy](advanced/merge-rules.md#custom-source-strategy).

### Field Merge Strategies

Per-field overrides via `field_merges` parameter. Maps `F[Config].field` to a strategy name, a plain `Callable[[list[JSONValue]], JSONValue]`, or any object implementing the public `FieldMergeStrategy` `Protocol`.

| Strategy | Behavior |
|----------|----------|
| `"first_wins"` | Keep the value from the first source. |
| `"last_wins"` | Keep the value from the last source. |
| `"append"` | Concatenate lists: `base + override`. |
| `"append_unique"` | Concatenate lists, removing duplicates. |
| `"prepend"` | Concatenate lists: `override + base`. |
| `"prepend_unique"` | Concatenate lists in reverse order, removing duplicates. |

The built-ins are also exposed as classes from `dature.strategies.field` (`FieldFirstWins`, `FieldLastWins`, `FieldAppend`, `FieldAppendUnique`, `FieldPrepend`, `FieldPrependUnique`). See [Custom Field Strategy](advanced/merge-rules.md#custom-field-strategy) for examples.

---

## Field Path

### `F`

Factory for building type-safe field paths. Used for `field_mapping`, `field_merges`, `field_groups`, `validators`, `skip_field_if_invalid`, and `nested_resolve`.

```python
--8<-- "examples/docs/api_reference/api_reference_field_path.py"
```

### `FieldPath`

Immutable dataclass (`frozen=True, slots=True`) created via `F[Config].field_name`.

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `type \| str` | The dataclass type (or its string name) this path belongs to. |
| `parts` | `tuple[str, ...]` | Sequence of field names forming the path. |

**Methods:**

| Method | Return type | Description |
|--------|-------------|-------------|
| `__getattr__(name)` | `FieldPath` | Chain to nested fields. Validates that the field exists on the owner dataclass. Returns a new `FieldPath` with extended parts. |
| `as_path()` | `str` | Dot-separated string representation (e.g. `"database.host"`). Raises `ValueError` if parts is empty. |

---

## Report

### `get_load_report()`

```python
--8<-- "src/dature/load_report.py:get-load-report"
```

Retrieves the `LoadReport` attached to a loaded instance. Returns `None` and emits a warning if `debug=True` was not passed to `load()`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `instance` | `Any` | The loaded dataclass instance (or the type in decorator mode on error). |

### `LoadReport`, `SourceEntry`, `FieldOrigin`

```python
--8<-- "src/dature/load_report.py:report-structure"
```

#### `SourceEntry`

Frozen dataclass describing one source in the load pipeline.

| Field | Type | Description |
|-------|------|-------------|
| `index` | `int` | Source position (0-based) in the `load()` call. |
| `file_path` | `str \| None` | File path string, or `None` for non-file sources. |
| `loader_type` | `str` | Source class name (e.g. `"JsonSource"`, `"EnvSource"`). |
| `raw_data` | `JSONValue` | Raw data loaded from this source before merging. |

#### `FieldOrigin`

Frozen dataclass describing which source provided a specific field value.

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Dot-separated field path (e.g. `"database.host"`). |
| `value` | `JSONValue` | The value that was used. |
| `source_index` | `int` | Index of the winning source. |
| `source_file` | `str \| None` | File path of the winning source. |
| `source_loader_type` | `str` | Class name of the winning source. |

#### `LoadReport`

Frozen dataclass with full load diagnostics.

| Field | Type | Description |
|-------|------|-------------|
| `dataclass_name` | `str` | Name of the target dataclass. |
| `strategy` | `MergeStrategyEnum \| None` | Merge strategy used, or `None` for single source. |
| `sources` | `tuple[SourceEntry, ...]` | All sources in order. |
| `field_origins` | `tuple[FieldOrigin, ...]` | Per-field origin info, sorted by key. |
| `merged_data` | `JSONValue` | Final merged data dict before dataclass conversion. |

---

## Configuration

### `configure()`

```python
--8<-- "src/dature/config.py:configure"
```

Set global configuration. Pass dicts to override specific options: `masking={"mask": "***"}`, `loading={"debug": True}`. `None` parameters keep their current values. Empty dict `{}` resets the group to defaults.

Global config is also loaded from `DATURE_*` environment variables on first access.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `masking` | `MaskingOptions \| None` | `None` | Secret masking options. |
| `error_display` | `ErrorDisplayOptions \| None` | `None` | Error formatting options. |
| `loading` | `LoadingOptions \| None` | `None` | Loading behavior options. |
| `type_loaders` | `TypeLoaderMap \| None` | `None` | Global custom type loaders `{type: callable}`. Merged with source-level loaders (source takes priority). |

### `MaskingConfig`

```python
--8<-- "src/dature/config.py:masking-config"
```

Frozen dataclass controlling secret masking behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mask` | `str` | `"<REDACTED>"` | Replacement string for masked values. Must be non-empty. |
| `visible_prefix` | `int` | `0` | Number of leading characters to keep visible. |
| `visible_suffix` | `int` | `0` | Number of trailing characters to keep visible. |
| `min_heuristic_length` | `int` | `8` | Minimum string length for heuristic-based detection. |
| `heuristic_threshold` | `float` | `0.5` | Entropy threshold for heuristic secret detection. |
| `secret_field_names` | `tuple[str, ...]` | `("password", "passwd", ...)` | Field name patterns that trigger masking. |
| `mask_secrets` | `bool` | `True` | Global on/off switch for masking. |

### `ErrorDisplayConfig`

```python
--8<-- "src/dature/config.py:error-display-config"
```

Frozen dataclass controlling error message formatting.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_visible_lines` | `int` | `3` | Maximum lines of source content shown in errors. |
| `max_line_length` | `int` | `80` | Maximum characters per line before truncation. |

### `LoadingConfig`

```python
--8<-- "src/dature/config.py:loading-config"
```

Frozen dataclass controlling load behavior defaults.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache` | `bool` | `True` | Default caching in decorator mode. |
| `debug` | `bool` | `False` | Default debug mode (collect `LoadReport`). |
| `nested_resolve_strategy` | `NestedResolveStrategy` | `"flat"` | Default nested resolve strategy for `FlatKeySource`. |
| `expand_env_vars` | `ExpandEnvVarsMode` | `"default"` | Default env var expansion mode applied when neither source nor load-level value is set. |

---

## Validators

All validators are frozen dataclasses (`frozen=True, slots=True`) with two methods:

| Method | Return type | Description |
|--------|-------------|-------------|
| `get_validator_func()` | `Callable` | Returns a function that takes the field value and returns `bool`. |
| `get_error_message()` | `str` | Returns the formatted error message. |

All validators accept an optional `error_message` parameter to override the default message. Use `{value}` / `{pattern}` placeholders in custom messages.

### Number Validators (`dature.validators.number`)

| Class | Parameter | Default message | Description |
|-------|-----------|-----------------|-------------|
| `Gt` | `value: int \| float` | `"Value must be greater than {value}"` | Strictly greater than. |
| `Ge` | `value: int \| float` | `"Value must be greater than or equal to {value}"` | Greater than or equal. |
| `Lt` | `value: int \| float` | `"Value must be less than {value}"` | Strictly less than. |
| `Le` | `value: int \| float` | `"Value must be less than or equal to {value}"` | Less than or equal. |

### String Validators (`dature.validators.string`)

| Class | Parameter | Default message | Description |
|-------|-----------|-----------------|-------------|
| `MinLength` | `value: int` | `"Value must have at least {value} characters"` | Minimum string length. |
| `MaxLength` | `value: int` | `"Value must have at most {value} characters"` | Maximum string length. |
| `RegexPattern` | `pattern: str` | `"Value must match pattern '{pattern}'"` | Full regex match (`re.match`). |

### Sequence Validators (`dature.validators.sequence`)

| Class | Parameter | Default message | Description |
|-------|-----------|-----------------|-------------|
| `MinItems` | `value: int` | `"Value must have at least {value} items"` | Minimum number of items. |
| `MaxItems` | `value: int` | `"Value must have at most {value} items"` | Maximum number of items. |
| `UniqueItems` | — | `"Value must contain unique items"` | All items must be unique. |

### Root Validator (`dature.validators.root`)

```python
--8<-- "src/dature/validators/root.py:root-validator"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `func` | `Callable[..., bool]` | — | Validation function. Receives the loaded dataclass instance, returns `True` if valid. |
| `error_message` | `str` | `"Root validation failed"` | Error message on failure. |

**Methods:** `get_validator_func()` → returns `func`. `get_error_message()` → returns `error_message`.

---

## Special Types

### `SecretStr`

Module: `dature.fields.secret_str`. A string wrapper that hides its value in `str()` and `repr()`.

| Method / Property | Return type | Description |
|-------------------|-------------|-------------|
| `SecretStr(secret_value)` | — | Constructor. Takes the raw secret string. |
| `get_secret_value()` | `str` | Returns the actual secret value. |
| `__str__()` | `str` | Returns `"**********"`. |
| `__repr__()` | `str` | Returns `"SecretStr('**********')"`. |
| `__len__()` | `int` | Length of the underlying secret. |
| `__eq__()`, `__hash__()` | — | Equality and hashing based on the secret value. |

### `ByteSize`

Module: `dature.fields.byte_size`. Parses human-readable byte sizes (`"1.5 GB"`, `"512 KiB"`) into an integer byte count.

**Accepted formats:** `<number><unit>` where unit is one of: `B`, `KB`, `MB`, `GB`, `TB`, `PB` (decimal) or `KiB`, `MiB`, `GiB`, `TiB`, `PiB` (binary). Case-insensitive. Whitespace between number and unit is allowed.

| Method / Property | Return type | Description |
|-------------------|-------------|-------------|
| `ByteSize(value)` | — | Constructor. Accepts `int` (raw bytes) or `str` (e.g. `"1.5 GB"`). |
| `human_readable(*, decimal=False)` | `str` | Format as human-readable string. `decimal=True` for KB/MB/GB, `False` for KiB/MiB/GiB. |
| `__int__()` | `int` | Raw byte count. |
| `__str__()` | `str` | Same as `human_readable()`. |
| `__repr__()` | `str` | Returns `"ByteSize(<bytes>)"`. |
| `__eq__()`, `__hash__()` | — | Equality and hashing based on byte count. |
| `__lt__()`, `__le__()`, `__gt__()`, `__ge__()` | `bool` | Comparison operators based on byte count. |

### `PaymentCardNumber`

Module: `dature.fields.payment_card`. Luhn-validated payment card number with brand detection.

Constructor strips spaces and dashes, validates digit-only 12–19 chars, and runs Luhn check. Raises `ValueError` on invalid input.

| Method / Property | Return type | Description |
|-------------------|-------------|-------------|
| `PaymentCardNumber(card_number)` | — | Constructor. Accepts string with digits, spaces, dashes. |
| `get_raw_number()` | `str` | Returns the cleaned digit-only number. |
| `masked` | `str` | Property. Returns `"************1234"` (last 4 digits visible). |
| `brand` | `str` | Property. Detected brand: `"Visa"`, `"Mastercard"`, `"American Express"`, `"Discover"`, `"JCB"`, `"Diners Club"`, `"UnionPay"`, `"Maestro"`, `"Mir"`, `"Troy"`, `"RuPay"`, `"Verve"`, or `"Unknown"`. |
| `__str__()` | `str` | Same as `masked`. |
| `__repr__()` | `str` | Returns `"PaymentCardNumber('<masked>')"`. |
| `__eq__()`, `__hash__()` | — | Equality and hashing based on the raw number. |

### Other Type Aliases

| Type | Module | Description |
|------|--------|-------------|
| `URL` | `dature.types` | Alias for `urllib.parse.ParseResult`. Parsed from URL strings. |
| `Base64UrlStr` | `dature.types` | `NewType` over `str`. Decoded from base64url-encoded strings. |
| `Base64UrlBytes` | `dature.types` | `NewType` over `bytes`. Decoded from base64url-encoded strings. |

---

## Source Classes

### File-based sources (inherit `FileSource`)

All file-based sources accept the `file` parameter from [`FileSource`](#filesourcesource) plus all common parameters from [`Source`](#source).

`file` accepts `str`, `Path`, or file-like objects (`StringIO`, `BytesIO`, any `TextIOBase`/`BufferedIOBase`/`RawIOBase`). When `file=None`, the path defaults to the current directory.

`file_display()` returns the path as string, `"<stream>"` for file-like objects, or `None` when `file=None`.

#### `JsonSource(FileSource)`

| | |
|---|---|
| **Format** | JSON |
| **Module** | `dature.sources.json_` |
| **Dependencies** | stdlib `json` |
| **Error label** | `FILE` |
| **String parsing** | `float`, `date`, `datetime`, `time`, `bytearray` from strings |

#### `Json5Source(FileSource)`

| | |
|---|---|
| **Format** | JSON5 (comments, trailing commas, unquoted keys) |
| **Module** | `dature.sources.json5_` |
| **Dependencies** | `json5` |
| **Error label** | `FILE` |
| **String parsing** | `str` (from JSON5 identifiers), `float`, `date`, `datetime`, `time`, `bytearray` from strings |

#### `Yaml11Source(FileSource)`

| | |
|---|---|
| **Format** | YAML 1.1 |
| **Module** | `dature.sources.yaml_` |
| **Dependencies** | `ruamel.yaml` |
| **Error label** | `FILE` |
| **Native types** | `date`, `datetime` parsed natively by YAML. `time` from int, `bytearray` from strings |

#### `Yaml12Source(FileSource)`

| | |
|---|---|
| **Format** | YAML 1.2 |
| **Module** | `dature.sources.yaml_` |
| **Dependencies** | `ruamel.yaml` |
| **Error label** | `FILE` |
| **Native types** | `date`, `datetime` parsed natively by YAML. `time`, `bytearray` from strings |

#### `Toml10Source(FileSource)`

| | |
|---|---|
| **Format** | TOML 1.0 |
| **Module** | `dature.sources.toml_` |
| **Dependencies** | `toml_rs` |
| **Error label** | `FILE` |
| **Native types** | `date`, `datetime`, `time` parsed natively by TOML. `bytearray`, `None`, `str \| None` from strings |

#### `Toml11Source(FileSource)`

| | |
|---|---|
| **Format** | TOML 1.1 |
| **Module** | `dature.sources.toml_` |
| **Dependencies** | `toml_rs` |
| **Error label** | `FILE` |
| **Native types** | `date`, `datetime`, `time` parsed natively by TOML. `bytearray`, `None`, `str \| None` from strings |

#### `IniSource(FileSource)`

| | |
|---|---|
| **Format** | INI (stdlib `configparser`) |
| **Module** | `dature.sources.ini_` |
| **Dependencies** | stdlib `configparser` |
| **Error label** | `FILE` |
| **String parsing** | All values are strings. Automatic parsing of `str`, `float`, `date`, `datetime`, `time`, `bytearray`, `bool`, `None`, `str \| None`. Nested JSON in values (`[...]`, `{...}`) is inferred. |

Section headers become top-level dict keys. Dotted sections (`database.pool`) create nested dicts. `prefix` selects a single section.

### Flat key-value sources (inherit `FlatKeySource`)

All flat key-value sources accept `nested_sep`, `nested_resolve_strategy` and `nested_resolve` from [`FlatKeySource`](#flatkeysourcesource) plus all common parameters from [`Source`](#source).

All values are strings. Automatic parsing of `str`, `float`, `date`, `datetime`, `time`, `bytearray`, `bool`, `None`, `str | None`. Nested JSON in values (`[...]`, `{...}`) is inferred.

Nesting is built from `nested_sep` (default `"__"`): `APP__DB__HOST=x` → `{"db": {"host": "x"}}`.

#### `EnvSource(FlatKeySource)`

| | |
|---|---|
| **Format** | Environment variables (`os.environ`) |
| **Module** | `dature.sources.env_` |
| **Dependencies** | — |
| **Error label** | `ENV` |

Keys are lowercased after stripping `prefix`. `resolve_location()` returns `env_var_name` instead of file/line info.

#### `EnvFileSource(FlatKeySource)`

| | |
|---|---|
| **Format** | `.env` files (`KEY=value`, `#` comments, quoted values) |
| **Module** | `dature.sources.env_` |
| **Dependencies** | — |
| **Error label** | `ENV FILE` |

Inherits from both `FileFieldMixin` and `EnvSource`, so accepts the `file` parameter. `resolve_location()` returns line range within the `.env` file.

#### `DockerSecretsSource(FlatKeySource)`

| | |
|---|---|
| **Format** | Docker secrets directory (one file per secret) |
| **Module** | `dature.sources.docker_secrets` |
| **Dependencies** | — |
| **Error label** | `SECRET FILE` |

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dir_` | `FilePath` | — | Path to the Docker secrets directory (e.g. `/run/secrets`). Required. |

Each file in `dir_` becomes a key (filename, lowercased) with the file content (stripped) as value. Subdirectories are skipped. `resolve_location()` returns the path `dir_/secret_name` as `file_path`.

---

## Exceptions

All exceptions are in `dature.errors`.

### `DatureError`

Base exception for all dature errors.

### `DatureConfigError(ExceptionGroup[DatureError])`

Aggregated config loading errors. Contains one or more `FieldLoadError` sub-exceptions.

| Field | Type | Description |
|-------|------|-------------|
| `dataclass_name` | `str` | Name of the target dataclass. |
| `exceptions` | `tuple[DatureError, ...]` | Individual errors (inherited from `ExceptionGroup`). |

`str()` returns `"<name> loading errors (<count>)"`.

### `FieldLoadError(DatureError)`

Single field loading error with source location.

| Field | Type | Description |
|-------|------|-------------|
| `field_path` | `list[str]` | Path to the field (e.g. `["database", "host"]`). |
| `message` | `str` | Human-readable error description. |
| `input_value` | `JSONValue` | The raw value that failed to load. |
| `locations` | `list[SourceLocation]` | Source locations for error reporting (file path, line range, env var name). |

`str()` returns a formatted multi-line message with source context and caret pointing at the value.

### `SourceLoadError(DatureError)`

Source-level loading failure (e.g. file not found, parse error).

| Field | Type | Description |
|-------|------|-------------|
| `message` | `str` | Error description. |
| `location` | `SourceLocation \| None` | Source location, if available. |

### `MergeConflictError(DatureConfigError)`

Raised with `strategy="raise_on_conflict"` when sources provide different values. Contains `MergeConflictFieldError` sub-exceptions.

### `MergeConflictFieldError(DatureError)`

Per-field merge conflict.

| Field | Type | Description |
|-------|------|-------------|
| `field_path` | `list[str]` | Path to the conflicting field. |
| `message` | `str` | Conflict description. |
| `locations` | `list[SourceLocation]` | Conflicting source locations. |

### `FieldGroupError(DatureConfigError)`

Field group constraint violation. Contains `FieldGroupViolationError` sub-exceptions.

### `FieldGroupViolationError(DatureError)`

Single field group violation.

| Field | Type | Description |
|-------|------|-------------|
| `group_fields` | `tuple[str, ...]` | All fields in the group. |
| `changed_fields` | `tuple[str, ...]` | Fields that were overridden. |
| `unchanged_fields` | `tuple[str, ...]` | Fields that were not overridden. |
| `changed_sources` | `tuple[str, ...]` | Source names for changed fields. |
| `unchanged_sources` | `tuple[str, ...]` | Source names for unchanged fields. |
| `source_index` | `int` | Index of the source that caused the violation. |

### `EnvVarExpandError(DatureConfigError)`

Missing environment variables in `expand_env_vars="strict"` mode. Contains `MissingEnvVarError` sub-exceptions.

### `MissingEnvVarError(DatureError)`

Single missing env var.

| Field | Type | Description |
|-------|------|-------------|
| `var_name` | `str` | Name of the missing variable. |
| `position` | `int` | Character position in the source string. |
| `source_text` | `str` | The original string containing `$VAR`. |
| `field_path` | `list[str]` | Field path, if known. |
| `location` | `SourceLocation \| None` | Source location, if available. |

### `SourceLocation`

Frozen dataclass used in error messages to point at the source of a value.

| Field | Type | Description |
|-------|------|-------------|
| `location_label` | `str` | Source type label: `"FILE"`, `"ENV"`, `"ENV FILE"`, `"SECRET FILE"`. |
| `file_path` | `Path \| None` | File path, or `None` for env vars. |
| `line_range` | `LineRange \| None` | Start/end line numbers in the file. |
| `line_content` | `list[str] \| None` | Relevant source lines for context. |
| `env_var_name` | `str \| None` | Environment variable name, for ENV sources. |
| `annotation` | `str \| None` | Extra annotation (e.g. merge conflict info). |
| `env_var_value` | `str \| None` | Raw env var value for conflict reporting. |

### `LineRange`

Frozen dataclass for file line ranges.

| Field | Type | Description |
|-------|------|-------------|
| `start` | `int` | Start line (1-based). |
| `end` | `int` | End line (1-based, inclusive). |

`repr()` returns `"line 5"` or `"line 5-8"`.

---

## Type Aliases

| Alias | Definition | Module |
|-------|------------|--------|
| `FileLike` | `TextIOBase \| BufferedIOBase \| RawIOBase` | `dature.types` |
| `FilePath` | `str \| Path` | `dature.types` |
| `FileOrStream` | `Path \| FileLike` | `dature.types` |
| `NameStyle` | `Literal["lower_snake", "upper_snake", "lower_camel", "upper_camel", "lower_kebab", "upper_kebab"]` | `dature.types` |
| `ExpandEnvVarsMode` | `Literal["disabled", "default", "empty", "strict"]` | `dature.types` |
| `FieldRef` | `FieldPath \| str \| int \| float \| bool \| list \| dict \| tuple \| set \| bytes \| None` | `dature.types` |
| `FieldMapping` | `dict[FieldRef, str \| tuple[str, ...]]` | `dature.types` |
| `FieldValidators` | `dict[FieldRef, ValidatorProtocol \| tuple[ValidatorProtocol, ...]]` | `dature.types` |
| `FieldMergeMap` | `dict[FieldRef, FieldMergeStrategyName \| Callable[..., Any]]` | `dature.types` |
| `FieldMergeCallable` | `Callable[[list[JSONValue]], JSONValue]` | `dature.types` |
| `FieldMergeStrategyName` | `Literal["first_wins", "last_wins", "append", "append_unique", "prepend", "prepend_unique"]` | `dature.types` |
| `FieldMergeStrategy` | `Protocol` with `__call__(values: list[JSONValue]) -> JSONValue` | `dature.strategies.field` |
| `FieldGroupTuple` | `tuple[FieldRef, ...]` | `dature.types` |
| `TypeLoaderMap` | `dict[type, Callable[..., Any]]` | `dature.types` |
| `MergeStrategyName` | `Literal["last_wins", "first_wins", "first_found", "raise_on_conflict"]` | `dature.types` |
| `SourceMergeStrategy` | `Protocol` with `__call__(sources: Sequence[Source], ctx: LoadCtx) -> JSONValue` | `dature.strategies.source` |
| `LoadCtx` | Helper passed to `SourceMergeStrategy.__call__`. Primary API: `ctx.merge(source=src, base=base, op=deep_merge_last_wins)` — applies one source to the running base, drives debug logs and `field_origins` automatically. Also: `ctx.load(src)` for raw access (cached), `ctx.field_origins()` for the accumulated `tuple[FieldOrigin, ...]`. | `dature.strategies.source` |
| `MergeStepEvent` | Frozen dataclass: `step_idx: int`, `source: Source`, `source_data: JSONValue`, `before: JSONValue`, `after: JSONValue`. Delivered to `LoadCtx(on_merge_step=...)` callback for each `ctx.merge` call. | `dature.strategies.source` |
| `NestedResolveStrategy` | `Literal["flat", "json"]` | `dature.types` |
| `NestedResolve` | `dict[NestedResolveStrategy, tuple[FieldPath \| Any, ...]]` | `dature.types` |
| `JSONValue` | `dict[str, JSONValue] \| list[JSONValue] \| str \| int \| float \| bool \| None` | `dature.types` |
| `LoadRawResult` | `dataclass(data: JSONValue, nested_conflicts: NestedConflicts)` | `dature.types` |
