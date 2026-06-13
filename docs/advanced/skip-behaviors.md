# Skip Behaviors

## Skipping Sources with Parse Errors

`skip_if_broken=True` silently skips a source whose file **exists but fails to parse** (invalid syntax, config error).

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/skip_behaviors/merging_skip_broken.py:example"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_defaults.yaml"
    ```

## Skipping Missing Sources

`skip_if_missing=True` silently skips a source whose file **does not exist**.

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/skip_behaviors/merging_skip_missing.py:example"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_defaults.yaml"
    ```

## Per-source Skip Overrides

Both `skip_if_broken` and `skip_if_missing` can be set directly on a `Source` instance, which takes priority over the global `load()` flag:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/skip_behaviors/merging_skip_broken_per_source.py:example"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_defaults.yaml"
    ```

If all sources fail to load, a `ValueError` is raised.

## Skipping Invalid Fields

Drop fields with invalid values and let other sources or defaults fill them in:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/skip_behaviors/merging_skip_invalid.py:example"
    ```

=== "merging_skip_invalid_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/skip_behaviors/sources/merging_skip_invalid_defaults.yaml"
    ```

Restrict skipping to specific fields:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/skip_behaviors/merging_skip_invalid_per_field.py:example"
    ```

=== "merging_skip_invalid_per_field_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/skip_behaviors/sources/merging_skip_invalid_per_field_defaults.yaml"
    ```

=== "merging_skip_invalid_per_field_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/skip_behaviors/sources/merging_skip_invalid_per_field_overrides.yaml"
    ```

Only `port` and `timeout` will be skipped if invalid; other fields still raise errors.

If a required field is invalid in all sources and has no default:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/skip_behaviors/merging_skip_invalid_required_error.py:example"
    ```

=== "merging_skip_invalid_required_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/skip_behaviors/sources/merging_skip_invalid_required_defaults.yaml"
    ```

=== "merging_skip_invalid_required_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/skip_behaviors/sources/merging_skip_invalid_required_overrides.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/skip_behaviors/merging_skip_invalid_required_error.stderr"
    ```
