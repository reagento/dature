# Debug & Reports

Pass `debug=True` to collect a `LoadReport`:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_debug_report.py"
    ```

=== "defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/defaults.yaml"
    ```

=== "overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/overrides.yaml"
    ```

## Report Structure

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

## Debug Logging

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

## Report on Error

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
