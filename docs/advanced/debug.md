# Debug & Reports

Pass `debug=True` to collect a `LoadReport`:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_debug_report.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/common_overrides.yaml"
    ```

## Report Structure

```python
--8<-- "src/dature/load_report.py:report-structure"
```

## Debug Logging

All loading steps are logged at `DEBUG` level under the `"dature"` logger regardless of the `debug` flag. Secret values are automatically masked:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_debug_logging.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/common_overrides.yaml"
    ```

## Report on Error

If loading fails with `DatureConfigError` and `debug=True` was passed, the report is attached to the dataclass type:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_debug_error.py"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/common_overrides.yaml"
    ```

=== "advanced_debug_error_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/advanced_debug_error_defaults.yaml"
    ```

Without `debug=True`, `get_load_report()` returns `None` and emits a warning.
