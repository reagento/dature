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
--8<-- "src/dature/load_report.py:report-structure"
```

## Debug Logging

All loading steps are logged at `DEBUG` level under the `"dature"` logger regardless of the `debug` flag. Secret values are automatically masked:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_debug_logging.py"
    ```

=== "defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/defaults.yaml"
    ```

=== "overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/overrides.yaml"
    ```

## Report on Error

If loading fails with `DatureConfigError` and `debug=True` was passed, the report is attached to the dataclass type:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_debug_error.py"
    ```

=== "overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/overrides.yaml"
    ```

=== "invalid_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/invalid_defaults.yaml"
    ```

Without `debug=True`, `get_load_report()` returns `None` and emits a warning.
