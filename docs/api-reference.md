# API Reference

## Core

### `dature.load()`

```python
--8<-- "src/dature/main.py:load"
```

Main entry point. Two calling patterns:

**Function mode** — pass `schema`, get an instance back:

```python
--8<-- "docs/examples/api_reference/api_reference_function_mode.py:example"
```

**Decorator mode** — omit `schema`, get a decorator:

```python
--8<-- "docs/examples/api_reference/api_reference_decorator_mode.py:example"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*sources` | `Source` | — | One or more source descriptors (e.g. `JsonSource(file=...)`, `EnvSource()`). Multiple sources → merge mode. |
| `schema` | `type[T] \| None` | `None` | Target dataclass. If provided → function mode. If `None` → decorator mode. |
| `cache` | `bool \| timedelta \| None` | `None` | Enable caching. `True`/`False` toggle, `timedelta` sets TTL. Default from `configure()`. **Effective in decorator mode only** — function mode `load(...)` creates a throwaway loader each call. For function-mode caching, use `dature.Loader` explicitly; see [Caching](advanced/caching.md). |
| `cache_engine` | `bool \| None` | `None` | Retain the compiled engine across loads (independent of `cache`, which caches the *result*). Default from `configure()`, itself defaulting to `False`. See [Caching](advanced/caching.md#cache_engine-retaining-the-compiled-engine). |
| `debug` | `bool \| None` | `None` | Collect `LoadReport` on the result instance. Default from `configure()`. Retrieve with `load_report()`. |
| `strategy` | `MergeStrategyName \| SourceMergeStrategy` | `"last_wins"` | Merge strategy: a built-in name or a custom object implementing `SourceMergeStrategy`. Only used with multiple sources. See [Merge Strategies](#merge-strategies). |
| `field_merges` | `FieldMergeMap \| None` | `None` | Per-field merge strategy overrides. Maps `F[Config].field` to a strategy name, callable, or any object implementing `FieldMergeStrategy`. See [Field Merge Strategies](#field-merge-strategies). |
| `field_groups` | `Sequence[FieldGroupTuple]` | `()` | Groups of fields that must change together. Each group is a sequence of `F[Config].field` references. |
| `skip_if_broken` | `bool` | `False` | Skip sources that fail to parse (invalid syntax, config error) instead of raising. |
| `skip_if_missing` | `bool` | `False` | Skip sources whose file does not exist instead of raising. |
| `skip_field_if_invalid` | `SkipFieldsInvalid` | `None` | Skip fields that fail validation instead of raising. `F.ANY` skips any invalid field, a sequence of `F[Config].field` skips only those, `None`/`[]` skip nothing. |
| `expand_env_vars` | `ExpandEnvVarsMode \| None` | `None` | Env var expansion mode applied to all sources. Source-level setting takes priority. |
| `secret_field_names` | `Sequence[str] \| None` | `None` | Extra secret field name patterns for masking. |
| `mask_secrets` | `bool \| None` | `None` | Enable/disable secret masking globally. |
| `type_loaders` | `TypeLoaderMap \| None` | `None` | Custom type loaders mapping types to conversion functions. Merged with source-level and global loaders. |
| `nested_resolve_strategy` | `NestedResolveStrategy \| None` | `None` | Default priority for JSON vs flat keys in `FlatKeySource`. See [Nested Resolve](advanced/nested-resolve.md). |
| `nested_resolve` | `NestedResolve \| None` | `None` | Per-field nested resolve strategy overrides. See [Nested Resolve](advanced/nested-resolve.md#per-field-strategy). |
| `root_validators` | `Iterable[RootPredicate]` | `()` | Post-load validation of the fully-constructed dataclass. Runs once after all sources have been merged. See [Validation](basic/validation.md#root-validators). |

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

### `dature.Loader`

```python
class Loader[T: DataclassInstance]:
    def __init__(*sources, schema, cache=None, cache_engine=None, debug=None, **load_kwargs): ...
    def load(self) -> T: ...
```

Public class that carries all the load-time parameters and the cache state. Use it for function-mode caching across repeated calls (the throwaway `Loader` constructed inside `dature.load(...)` cannot cache between calls). Constructor accepts the same parameters as `dature.load(..., schema=...)` for function mode. See [Caching](advanced/caching.md) for the cache semantics (eternal / TTL / bucket-aligned).

---

### `Source`

```python
--8<-- "src/dature/sources/base/source.py:load-metadata"
```

Abstract base class for all sources. See [Introduction — Source Reference](introduction.md#source-reference) for parameter descriptions.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prefix` | `DotSeparatedPath \| None` | `None` | Filter ENV keys (`"APP_"`) or extract nested object (`"app.database"`). |
| `name_style` | `NameStyle \| None` | `None` | Naming convention mapping: `"lower_snake"`, `"upper_snake"`, `"lower_camel"`, `"upper_camel"`, `"lower_kebab"`, `"upper_kebab"`. |
| `field_mapping` | `FieldMapping \| None` | `None` | Explicit field renaming with `F` objects. |
| `validators` | `FieldValidators \| None` | `None` | Per-field validators via `Annotated` metadata or explicit mapping. |
| `expand_env_vars` | `ExpandEnvVarsMode \| None` | `None` | ENV variable expansion: `"disabled"`, `"default"`, `"empty"`, `"strict"`. |
| `skip_field_if_invalid` | `SkipFieldsInvalid` | `None` | Skip invalid fields from this source. `F.ANY` for all, a sequence of `F[Config].field` for specific ones, `None` delegates to the load-level default. |
| `type_loaders` | `TypeLoaderMap \| None` | `None` | Custom type converters `{type: callable}` for this source. |
| `tag` | `str \| None` | `None` | Explicit tag for `${@tag.key}` cross-refs. Defaults to the format name. See [Cross-Source References](advanced/cross_source_refs.md). |
| `when` | `Condition \| None` | `None` | Include this source only when a condition is met, built with the `When()` DSL. A non-`Condition` value raises `TypeError`. See [Conditional Sources](advanced/conditional_sources.md). |

**Public methods:**

| Method | Return type | Description |
|--------|-------------|-------------|
| `load_raw()` | `LoadRawResult` | Load raw data, apply prefix filtering and env var expansion. Returns `LoadRawResult(data, nested_conflicts)`. |
| `file_display()` | `str \| None` | Human-readable file identifier for logging. Returns `None` by default. |
| `file_path_for_errors()` | `Path \| None` | File path used in error messages. Returns `None` by default. |
| `resolve_location(...)` | `list[SourceLocation]` | Locate a field in the source content for error reporting. Returns `SourceLocation` with line range, env var name, etc. |

### `FileSource(Source)`

Base class for file-based sources (`JsonSource`, `Yaml11Source`, `Toml10Source`, `IniSource`, etc.).

```python
--8<-- "src/dature/sources/base/file.py:file-source"
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
--8<-- "src/dature/sources/base/flat_key.py:flat-key-source"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `nested_sep` | `str` | `"__"` | Separator for nested key splitting. `APP__DB__HOST` → `{"db": {"host": ...}}` |
| `nested_resolve_strategy` | `NestedResolveStrategy \| None` | `None` | Priority when both flat and JSON keys exist: `"flat"` or `"json"`. Falls back to `configure()`'s `LoadingConfig.nested_resolve_strategy` (default `"flat"`). See [Nested Resolve](advanced/nested-resolve.md). |
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

The built-ins are also exposed as classes from `dature.strategies.source` (`SourceLastWins`, `SourceFirstWins`, `SourceFirstFound`, `SourceRaiseOnConflict`) implementing the public `SourceMergeStrategy` `Protocol`. Pass any object satisfying that protocol as `strategy` for custom merge logic — see [Custom Source Strategy](advanced/merge-strategies.md#custom-source-strategy).

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

The built-ins are also exposed as classes from `dature.strategies.field` (`FieldFirstWins`, `FieldLastWins`, `FieldAppend`, `FieldAppendUnique`, `FieldPrepend`, `FieldPrependUnique`). See [Custom Field Strategy](advanced/merge-strategies.md#custom-field-strategy) for examples.

---

## Field Path

### `F`

Factory for building type-safe field paths. Used for `field_mapping`, `field_merges`, `field_groups`, `validators`, `skip_field_if_invalid`, and `nested_resolve`.

```python
--8<-- "docs/examples/api_reference/api_reference_field_path.py"
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

### `load_report()`

```python
--8<-- "src/dature/report.py:load-report"
```

Retrieves the `LoadReport` attached to a loaded instance. Returns `None` and emits a warning if `debug=True` was not passed to `load()`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `instance` | `Any` | The loaded dataclass instance (or the type in decorator mode on error). |

### `LoadReport`, `SourceEntry`, `FieldOrigin`

```python
--8<-- "src/dature/report_types.py:value-types"
--8<-- "src/dature/report.py:report-structure"
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
| `vault` | `VaultOptions \| None` | `None` | Vault connection defaults, used by `VaultSource` when its own fields are unset. |
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
| `cache` | `bool \| timedelta` | `True` | Default caching. `True`/`False` toggle, `timedelta` sets TTL. See [Caching](advanced/caching.md). |
| `cache_engine` | `bool` | `False` | Default engine retention. See [Caching](advanced/caching.md#cache_engine-retaining-the-compiled-engine). |
| `debug` | `bool` | `False` | Default debug mode (collect `LoadReport`). |
| `nested_resolve_strategy` | `NestedResolveStrategy` | `"flat"` | Default nested resolve strategy for `FlatKeySource`. |
| `expand_env_vars` | `ExpandEnvVarsMode` | `"default"` | Default env var expansion mode applied when neither source nor load-level value is set. |
| `search_system_paths` | `bool` | `True` | Whether file sources search OS-specific config directories by default. See [Config Search](advanced/config-search.md). |
| `system_config_dirs` | `SystemConfigDirsArg` | per-OS defaults | Directories searched per platform (`linux`/`darwin`/`win32`) when `search_system_paths` is enabled. |
| `encoding` | `str \| None` | `None` | Default text encoding for file sources. |

### `VaultConfig`

```python
--8<-- "src/dature/config.py:vault-config"
```

Frozen dataclass with connection defaults for `VaultSource`. Fields left unset on a
`VaultSource` instance fall back to these values.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | `str \| None` | `None` | Vault server address. |
| `token` | `str \| None` | `None` | Vault token for authentication. |
| `role_id` | `str \| None` | `None` | AppRole `role_id`, used with `secret_id` instead of `token`. |
| `secret_id` | `str \| None` | `None` | AppRole `secret_id`, used with `role_id` instead of `token`. |
| `namespace` | `str \| None` | `None` | Vault Enterprise namespace. |
| `verify` | `bool \| str` | `True` | TLS verification: `True`/`False`, or a path to a CA bundle. |
| `mount_point` | `str` | `"secret"` | Secrets engine mount point. |
| `kv_version` | `Literal[1, 2]` | `2` | KV secrets engine version. |

---

## Validators

Validators are built with the `V` DSL (`dature.validators.v.V`), used inside
`Annotated[T, <predicate>]` field metadata:

```python
from dataclasses import dataclass
from typing import Annotated

from dature import V


@dataclass
class ServiceConfig:
    port: Annotated[int, (V >= 1) & (V <= 65535)]
    name: Annotated[str, (V.len() >= 3) & (V.len() <= 50)]
    tags: Annotated[list[str], V.unique_items() & V.each(V.len() >= 3)]
```

All predicates are frozen dataclasses (`frozen=True, slots=True`) with two methods:

| Method | Return type | Description |
|--------|-------------|-------------|
| `get_validator_func()` | `Callable` | Returns a function that takes the field value and returns `bool`. |
| `get_error_message()` | `str` | Returns the formatted error message. |

All predicates accept an optional `error_message` keyword to override the default message
(placeholders like `{value}` / `{pattern}` are filled in from the predicate's own
parameters). `with_error_message(message)` returns a copy with the message replaced —
raises `TypeError` on composite predicates (`&`/`\|`/`~`), since they derive their
message from their children.

!!! warning
    Chained comparisons like `3 <= V.len() <= 10` are **not** supported — Python's
    `and`-based chaining semantics silently break them. Use `(V.len() >= 3) & (V.len() <= 10)`.

### Comparison

`V <op> value` builds a `ComparePredicate`; `V.len() <op> value` builds a
`LengthComparePredicate` (raises `ValidatorTypeError` at schema-build time if the field
type doesn't support `len()`).

| Operator | Default message |
|----------|-----------------|
| `V >= x` / `V.len() >= n` | `"Value must be greater than or equal to {value}"` / `"...length must be..."` |
| `V > x` / `V.len() > n` | `"Value must be greater than {value}"` / `"...length must be..."` |
| `V <= x` / `V.len() <= n` | `"Value must be less than or equal to {value}"` / `"...length must be..."` |
| `V < x` / `V.len() < n` | `"Value must be less than {value}"` / `"...length must be..."` |
| `V == x` | `"Value must equal {value}"` |
| `V != x` | `"Value must not equal {value}"` |

### Other predicates

| Method | Predicate | Default message | Description |
|--------|-----------|-----------------|-------------|
| `V.in_(values, *, error_message=None)` | `InPredicate` | `"Value must be one of: {rendered}"` | Value must be one of `values`. |
| `V.matches(pattern, *, error_message=None)` | `MatchesPredicate` | `"Value must match pattern '{pattern}'"` | Full regex match (`re.match`). Field type must be `str`, else `ValidatorTypeError`. |
| `V.unique_items(*, error_message=None)` | `UniqueItemsPredicate` | `"Value must contain unique items"` | All items in a collection must be unique. Field type must support collections, else `ValidatorTypeError`. |
| `V.each(inner, *, error_message=None)` | `EachPredicate` | inner predicate's message | Applies `inner` to every element. Field type must support iteration, else `ValidatorTypeError`. |
| `V.check(func, *, error_message)` | `CustomPredicate` | required (no default) | Escape hatch: `func(value) -> bool`, no type checking. |
| `V.root(func, *, error_message="Root validation failed")` | `RootPredicate` | `"Root validation failed"` | See below. |

### Composition

Predicates compose with `&` (`AndPredicate`), `\|` (`OrPredicate`), and `~`
(`NotPredicate`) — all fail-fast on `check_type`/short-circuit on the validator
function.

### Root Validator

```python
--8<-- "src/dature/validators/root.py"
```

`V.root(func, error_message=...)` builds a `RootPredicate`. Unlike the other predicates,
`RootPredicate` is **not** a `Predicate` subclass and cannot be placed in
`Annotated[...]` metadata — doing so raises `TypeError` at retort-build time. It may
only be used in `Source.root_validators` or `load(root_validators=...)`, and receives
the fully-loaded dataclass instance:

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
| `URL` | `dature.type_aliases` | Alias for `urllib.parse.ParseResult`. Parsed from URL strings. |
| `Base64UrlStr` | `dature.type_aliases` | PEP 695 `type` alias for `str`. Decoded from base64url-encoded strings. |
| `Base64UrlBytes` | `dature.type_aliases` | PEP 695 `type` alias for `bytes`. Decoded from base64url-encoded strings. |

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

Each file in `dir_` becomes a key (filename, lowercased) with the file content (stripped) as value. Subdirectories are skipped. `resolve_location()` returns the path `dir_/secret_name` as `file_path`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dir_` | `FilePath` | — | Path to the Docker secrets directory (e.g. `/run/secrets`). Required. |
| `encoding` | `str \| None` | `None` | Text encoding used to read each secret file. |

### CLI sources (inherit `CliSource`)

All CLI sources accept the common parameters from [`Source`](#source). `CliSource`
overrides `FlatKeySource`'s defaults: `nested_sep` defaults to `"--"` and
`expand_env_vars` defaults to `"disabled"` (the shell already expands `$VAR` before
argv reaches the parser).

#### `ArgparseSource(CliSource)`

| | |
|---|---|
| **Format** | `argparse` command lines, including subparsers |
| **Module** | `dature.sources.argparse_` |
| **Dependencies** | stdlib `argparse` |
| **Error label** | `CLI` |

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `parser` | `argparse.ArgumentParser` | — | Parser to read argv with. May have arbitrarily nested subparsers. Required. |

Unset defaults (`argparse.SUPPRESS`) are suppressed so they don't leak into merge
mode; explicit `bool` flags are kept. Subcommands emit a discriminator field plus
their own prefixed sub-arguments.

### Remote sources (inherit `RemoteSource`)

All remote sources accept the common parameters from [`Source`](#source). Values are
fetched over the network via `_fetch()` rather than read from a local file.

#### `VaultSource(RemoteSource)`

| | |
|---|---|
| **Format** | HashiCorp Vault KV secrets engine (v1 or v2) |
| **Module** | `dature.sources.vault_` |
| **Dependencies** | `hvac` |
| **Error label** | `VAULT` |

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | — | Secret path within the mount. Required. |
| `url` | `str \| None` | `None` | Vault server address. Falls back to `VaultConfig.url`; required (directly or via config). |
| `mount_point` | `str \| None` | `None` | Secrets engine mount point. Falls back to `VaultConfig.mount_point`. |
| `kv_version` | `Literal[1, 2] \| None` | `None` | KV engine version. Falls back to `VaultConfig.kv_version`. |
| `token` | `str \| None` | `None` | Vault token. Mutually exclusive with `role_id`/`secret_id`. |
| `role_id` | `str \| None` | `None` | AppRole `role_id`. Mutually exclusive with `token`. |
| `secret_id` | `str \| None` | `None` | AppRole `secret_id`. Mutually exclusive with `token`. |
| `namespace` | `str \| None` | `None` | Vault Enterprise namespace. |
| `verify` | `bool \| str \| None` | `None` | TLS verification: `True`/`False`, or a CA bundle path. Falls back to `VaultConfig.verify`. |

Requires either `token` or `role_id`+`secret_id` (raises at construction if neither or
both are given). Raises `KeyError` on an invalid path, `PermissionError` on a
forbidden/unauthorized response. See [`VaultConfig`](#vaultconfig) for global defaults.

---

## Exceptions

All exceptions are in `dature.errors`.

### `DatureError`

Base exception for all dature errors.

### `ValidatorTypeError(DatureError)`

Raised at schema-build time (not data-loading time) when a `V` predicate is
incompatible with a field's type — e.g. `V.len()` applied to an `int` field. Signals
that the schema itself is ill-formed; raised before any configuration data is read.

| Field | Type | Description |
|-------|------|-------------|
| `field_path` | `list[str]` | Path to the offending field. |
| `message` | `str` | Human-readable description of the incompatibility. |

### `DatureErrorGroup(ExceptionGroup[DatureError])`

Base for all dature exception groups. Subclasses add domain-specific context; see
`DatureConfigError`, `EnvVarExpandError`, `CrossRefExpandError` below.

### `DatureConfigError(DatureErrorGroup)`

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

### `EnvVarExpandError(DatureErrorGroup)`

Missing environment variables in `expand_env_vars="strict"` mode. Contains
`MissingEnvVarError` sub-exceptions. The exception actually raised during config
loading is `ConfigEnvVarExpandError` (below), which also carries `dataclass_name`.

### `ConfigEnvVarExpandError(EnvVarExpandError, DatureConfigError)`

The concrete exception raised by `load()`/`Loader.load()` when env var expansion fails
in strict mode. `str()` returns `"<dataclass_name> env expand errors (<count>)"`.

### `MissingEnvVarError(DatureError)`

Single missing env var.

| Field | Type | Description |
|-------|------|-------------|
| `var_name` | `str` | Name of the missing variable. |
| `position` | `int` | Character position in the source string. |
| `source_text` | `str` | The original string containing `$VAR`. |
| `field_path` | `list[str]` | Field path, if known. |
| `location` | `SourceLocation \| None` | Source location, if available. |

### `CrossRefError(DatureError)`

Single failure resolving a `${@tag.key}` cross-source reference — see
[Cross-Source References](advanced/cross_source_refs.md).

| Field | Type | Description |
|-------|------|-------------|
| `ref` | `str` | The raw `@tag.key` reference string. |
| `message` | `str` | Human-readable failure description. |
| `field_path` | `list[str]` | Field path, if known. |

### `CrossRefExpandError(DatureErrorGroup)`

Aggregated cross-source reference errors. Contains one or more `CrossRefError`
sub-exceptions.

### `SourceLocation`

Frozen dataclass used in error messages to point at the source of a value.

| Field | Type | Description |
|-------|------|-------------|
| `location_label` | `str` | Source type label: `"FILE"`, `"ENV"`, `"ENV FILE"`, `"SECRET FILE"`, `"CLI"`, `"VAULT"`, or a custom `RemoteSource` subclass's label. |
| `file_path` | `Path \| None` | File path, or `None` for env vars. |
| `line_range` | `LineRange \| None` | Start/end line numbers in the file. |
| `line_content` | `list[str] \| None` | Relevant source lines for context. |
| `env_var_name` | `str \| None` | Environment variable name, for ENV sources. |
| `annotation` | `str \| None` | Extra annotation (e.g. merge conflict info). |
| `env_var_value` | `str \| None` | Raw env var value for conflict reporting. |
| `line_carets` | `list[CaretSpan] \| None` | `^^^`-style caret spans pointing at the offending substring(s) within `line_content`. |

### `LineRange`

Frozen dataclass for file line ranges.

| Field | Type | Description |
|-------|------|-------------|
| `start` | `int` | Start line (1-based). |
| `end` | `int` | End line (1-based, inclusive). |

`repr()` returns `"line 5"` or `"line 5-8"`.

### `CaretSpan`

Frozen dataclass describing a `^^^` caret span within a `SourceLocation.line_content`
line. Re-exported via `dature.errors`.

| Field | Type | Description |
|-------|------|-------------|
| `start` | `int` | Start column of the span. |
| `end` | `int` | End column of the span. |
| `length` | `int` | Property. `end - start`. |

---

## Type Aliases

| Alias | Definition | Module |
|-------|------------|--------|
| `FileLike` | `TextIOBase \| BufferedIOBase \| RawIOBase` | `dature.type_aliases` |
| `FilePath` | `str \| Path` | `dature.type_aliases` |
| `FileOrStream` | `Path \| FileLike` | `dature.type_aliases` |
| `NameStyle` | `Literal["lower_snake", "upper_snake", "lower_camel", "upper_camel", "lower_kebab", "upper_kebab"]` | `dature.type_aliases` |
| `ExpandEnvVarsMode` | `Literal["disabled", "default", "empty", "strict"]` | `dature.type_aliases` |
| `FieldRef` | `FieldPath \| str \| int \| float \| bool \| list \| dict \| tuple \| set \| bytes \| None` | `dature.type_aliases` |
| `FieldMapping` | `dict[FieldRef, str \| Sequence[str]]` | `dature.type_aliases` |
| `FieldValidators` | `dict[FieldRef, ValidatorProtocol \| tuple[ValidatorProtocol, ...]]` | `dature.type_aliases` |
| `FieldMergeMap` | `dict[FieldRef, FieldMergeStrategyName \| Callable[..., Any]]` | `dature.type_aliases` |
| `FieldMergeCallable` | `Callable[[list[JSONValue]], JSONValue]` | `dature.type_aliases` |
| `FieldMergeStrategyName` | `Literal["first_wins", "last_wins", "append", "append_unique", "prepend", "prepend_unique"]` | `dature.type_aliases` |
| `FieldMergeStrategy` | `Protocol` with `__call__(values: list[JSONValue]) -> JSONValue` | `dature.strategies.field` |
| `FieldGroupTuple` | `Sequence[FieldRef]` | `dature.type_aliases` |
| `TypeLoaderMap` | `dict[type, Callable[..., Any]]` | `dature.type_aliases` |
| `MergeStrategyName` | `Literal["last_wins", "first_wins", "first_found", "raise_on_conflict"]` | `dature.type_aliases` |
| `SourceMergeStrategy` | `Protocol` with `__call__(sources: Sequence[Source], ctx: LoadCtx) -> JSONValue` | `dature.strategies.source` |
| `LoadCtx` | Helper passed to `SourceMergeStrategy.__call__`. Primary API: `ctx.merge(source=src, base=base, op=deep_merge_last_wins)` — applies one source to the running base, drives debug logs and `field_origins` automatically. Also: `ctx.load(src)` for raw access (cached), `ctx.field_origins()` for the accumulated `tuple[FieldOrigin, ...]`. | `dature.strategies.source` |
| `MergeStepEvent` | Frozen dataclass: `step_idx: int`, `source: Source`, `source_data: JSONValue`, `before: JSONValue`, `after: JSONValue`. Delivered to `LoadCtx(on_merge_step=...)` callback for each `ctx.merge` call. | `dature.strategies.source` |
| `NestedResolveStrategy` | `Literal["flat", "json"]` | `dature.type_aliases` |
| `NestedResolve` | `dict[NestedResolveStrategy, tuple[FieldPath \| Any, ...]]` | `dature.type_aliases` |
| `JSONValue` | `dict[str, JSONValue] \| list[JSONValue] \| str \| int \| float \| bool \| None` | `dature.type_aliases` |
| `LoadRawResult` | `dataclass(data: JSONValue, nested_conflicts: NestedConflicts)` | `dature.type_aliases` |
