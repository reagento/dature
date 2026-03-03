# Advanced

## Per-Field Merge Rules

Override the global merge strategy for individual fields. All available `FieldMergeStrategy` values:

| Strategy | Behavior |
|----------|----------|
| `FIRST_WINS` | Keep the value from the first source |
| `LAST_WINS` | Keep the value from the last source |
| `APPEND` | Concatenate lists: `base + override` |
| `APPEND_UNIQUE` | Concatenate lists, removing duplicates |
| `PREPEND` | Concatenate lists: `override + base` |
| `PREPEND_UNIQUE` | Concatenate lists in reverse order, removing duplicates |

```python
--8<-- "examples/docs/advanced_merge_rules.py"
```

### With RAISE_ON_CONFLICT

Fields with an explicit strategy are excluded from conflict detection:

```python
config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_="a.yaml"),
            LoadMetadata(file_="b.yaml"),
        ),
        strategy=MergeStrategy.RAISE_ON_CONFLICT,
        field_merges=(
            MergeRule(F[Config].host, FieldMergeStrategy.LAST_WINS),
        ),
    ),
    Config,
)
# "host" can differ between sources without raising an error,
# all other fields still raise MergeConflictError on conflict.
```

### Callable Merge

You can also pass a callable as the strategy:

```python
MergeRule(
    F[Config].tags,
    lambda values: sorted(set(v for lst in values for v in lst)),
)
```

The callable receives a `list[JSONValue]` (one value per source) and returns the merged value.

## Field Groups

Ensure related fields are always overridden together:

```python
--8<-- "examples/docs/advanced_field_groups_nested.py"
```

### Nested Dataclass Expansion

Passing a dataclass field expands it into all its leaf fields:

```python
@dataclass
class Database:
    host: str
    port: int

@dataclass
class Config:
    database: Database
    timeout: int

# FieldGroup(F[Config].database, F[Config].timeout)
# expands to (database.host, database.port, timeout)
```

### Multiple Groups

Multiple groups can be defined independently:

```python
field_groups=(
    FieldGroup(F[Config].host, F[Config].port),
    FieldGroup(F[Config].user, F[Config].password),
)
```

Field groups work with all merge strategies and can be combined with `field_merges`.

## Debug / LoadReport

Pass `debug=True` to collect a `LoadReport`:

```python
--8<-- "examples/docs/advanced_debug_report.py"
```

### Report Structure

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LoadReport:
    dataclass_name: str
    strategy: MergeStrategy | None
    sources: tuple[SourceEntry, ...]
    field_origins: tuple[FieldOrigin, ...]
    merged_data: JSONValue

@dataclass(frozen=True, slots=True, kw_only=True)
class SourceEntry:
    index: int
    file_path: str | None
    loader_type: str
    raw_data: JSONValue

@dataclass(frozen=True, slots=True, kw_only=True)
class FieldOrigin:
    key: str
    value: JSONValue
    source_index: int
    source_file: str | None
    source_loader_type: str
```

### Debug Logging

All loading steps are logged at `DEBUG` level under the `"dature"` logger regardless of the `debug` flag. Secret values are automatically masked:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

config = load(LoadMetadata(file_="config.json"), Config)
```

Example output for a two-source merge:

```
[Config] Source 0 loaded: loader=json, file=defaults.json, keys=['host', 'port']
[Config] Source 0 raw data: {'host': 'localhost', 'port': 3000}
[Config] Source 1 loaded: loader=json, file=overrides.json, keys=['port']
[Config] Source 1 raw data: {'port': 8080}
[Config] Merged result (strategy=last_wins, 2 sources): {'host': 'localhost', 'port': 8080}
[Config] Field 'host' = 'localhost'  <-- source 0 (defaults.json)
[Config] Field 'port' = 8080  <-- source 1 (overrides.json)
```

### Report on Error

If loading fails with `DatureConfigError` and `debug=True` was passed, the report is attached to the dataclass type:

```python
from dature.errors.exceptions import DatureConfigError

try:
    config = load(MergeMetadata(sources=(...,)), Config, debug=True)
except DatureConfigError:
    report = get_load_report(Config)
    # report.sources contains raw data from each source
    # report.merged_data contains the merged dict that failed to convert
```

Without `debug=True`, `get_load_report()` returns `None` and emits a warning.

## ENV Variable Expansion

String values in all file formats support environment variable expansion:

```python
--8<-- "examples/docs/advanced_env_expansion.py"
```

### Supported Syntax

| Syntax | Description |
|--------|-------------|
| `$VAR` | Simple variable |
| `${VAR}` | Braced variable |
| `${VAR:-default}` | Variable with fallback value |
| `${VAR:-$FALLBACK_VAR}` | Fallback is also an env variable |
| `%VAR%` | Windows-style variable |
| `$$` | Literal `$` (escaped) |
| `%%` | Literal `%` (escaped) |

### Expansion Modes

| Mode | Missing variable |
|------|------------------|
| `"default"` | Kept as-is (`$VAR` stays `$VAR`) |
| `"empty"` | Replaced with `""` |
| `"strict"` | Raises `EnvVarExpandError` |
| `"disabled"` | No expansion at all |

Set the mode on `LoadMetadata`:

```python
config = load(LoadMetadata(file_="config.yaml", expand_env_vars="strict"), Config)
```

For merge mode, set on `MergeMetadata` as default for all sources:

```python
config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_="defaults.yaml"),
            LoadMetadata(file_="overrides.yaml", expand_env_vars="disabled"),  # override per source
        ),
        expand_env_vars="strict",  # default for all sources
    ),
    Config,
)
```

In `"strict"` mode, all missing variables are collected and reported at once:

```
Missing environment variables (2):
  - DATABASE_URL (position 0 in '$DATABASE_URL')
  - SECRET_KEY (position 0 in '${SECRET_KEY}')
```

The `${VAR:-default}` fallback syntax works in all modes.

## Special Types

### SecretStr

See [Masking — SecretStr](masking.md#secretstr).

### ByteSize

Parses human-readable sizes:

```python
from dature.fields.byte_size import ByteSize

@dataclass
class Config:
    max_upload: ByteSize

# config.yaml: { max_upload: "1.5 GB" }
```

Supported units: B, KB, MB, GB, TB, PB, KiB, MiB, GiB, TiB, PiB.

### PaymentCardNumber

Validates using the Luhn algorithm and detects the brand:

```python
from dature.fields.payment_card import PaymentCardNumber

@dataclass
class Config:
    card: PaymentCardNumber

config = load(meta, Config)
print(config.card.brand)   # Visa
print(config.card.masked)  # ************1111
```

### URL

Parsed into `urllib.parse.ParseResult`:

```python
from dature.types import URL

@dataclass
class Config:
    api_url: URL

config = load(meta, Config)
print(config.api_url.scheme)  # https
print(config.api_url.netloc)  # api.example.com
```

### Base64UrlBytes / Base64UrlStr

Decoded from Base64 string in the config:

```python
from dature.types import Base64UrlBytes, Base64UrlStr

@dataclass
class Config:
    token: Base64UrlStr      # decoded to str
    data: Base64UrlBytes     # decoded to bytes
```

Full example:

```python
--8<-- "examples/docs/advanced_special_types.py"
```

## Caching

In decorator mode, caching is enabled by default:

```python
--8<-- "examples/docs/advanced_caching.py"
```

Caching can also be configured globally via `configure()`.

## Global configure()

Customize defaults for the entire application — programmatically or via environment variables:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_configure.py"
    ```

=== "Environment Variables"

    dature auto-loads its own config from `DATURE_*` environment variables on first use. Nested fields use `__` as delimiter:

    ```bash
    export DATURE_MASKING__MASK_CHAR="X"
    export DATURE_MASKING__MIN_VISIBLE_CHARS="1"
    export DATURE_ERROR_DISPLAY__MAX_VISIBLE_LINES="5"
    export DATURE_LOADING__DEBUG="false"
    export DATURE_LOADING__CACHE="true"
    ```

    ```python
    --8<-- "examples/docs/advanced_configure_env.py"
    ```

### MaskingConfig

```python
@dataclass(frozen=True, slots=True)
class MaskingConfig:
    mask_char: str = "*"
    min_visible_chars: int = 2
    min_length_for_partial_mask: int = 5
    fixed_mask_length: int = 5
    min_heuristic_length: int = 8
    secret_field_names: tuple[str, ...] = (
        "password", "passwd", "secret", "token",
        "api_key", "apikey", "api_secret", "access_key",
        "private_key", "auth", "credential",
    )
    mask_secrets: bool = True
```

### ErrorDisplayConfig

```python
@dataclass(frozen=True, slots=True)
class ErrorDisplayConfig:
    max_visible_lines: int = 3
    max_line_length: int = 80
```

### LoadingConfig

```python
@dataclass(frozen=True, slots=True)
class LoadingConfig:
    cache: bool = True
    debug: bool = False
```
