# Merge Rules

Override the global merge strategy for individual fields. All available `FieldMergeStrategy` values:

| Strategy | Behavior |
|----------|----------|
| `FIRST_WINS` | Keep the value from the first source |
| `LAST_WINS` | Keep the value from the last source |
| `APPEND` | Concatenate lists: `base + override` |
| `APPEND_UNIQUE` | Concatenate lists, removing duplicates |
| `PREPEND` | Concatenate lists: `override + base` |
| `PREPEND_UNIQUE` | Concatenate lists in reverse order, removing duplicates |

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_merge_rules.py"
    ```

=== "defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/defaults.yaml"
    ```

=== "overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/overrides.yaml"
    ```

## With RAISE_ON_CONFLICT

Fields with an explicit strategy are excluded from conflict detection:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_merge_rules_conflict.py"
    ```

=== "defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/defaults.yaml"
    ```

=== "overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/overrides.yaml"
    ```

## Callable Merge

You can also pass a callable as the strategy:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_merge_rules_callable.py"
    ```

=== "defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/defaults.yaml"
    ```

=== "overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/overrides.yaml"
    ```

The callable receives a `list[JSONValue]` (one value per source) and returns the merged value.

## Skipping Broken Sources

Skip sources that fail to load (missing file, invalid syntax):

=== "Python"

    ```python
    --8<-- "examples/docs/merging_skip_broken.py"
    ```

=== "defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/defaults.yaml"
    ```

Override per source with `skip_if_broken` on `LoadMetadata` (takes priority over the global flag):

=== "Python"

    ```python
    --8<-- "examples/docs/merging_skip_broken_per_source.py"
    ```

=== "defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/defaults.yaml"
    ```

If all sources fail to load, a `ValueError` is raised.

## Skipping Invalid Fields

Drop fields with invalid values and let other sources or defaults fill them in:

=== "Python"

    ```python
    --8<-- "examples/docs/merging_skip_invalid.py"
    ```

=== "skip_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/skip_defaults.yaml"
    ```

Restrict skipping to specific fields:

=== "Python"

    ```python
    --8<-- "examples/docs/merging_skip_invalid_per_field.py"
    ```

=== "skip_specific_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/skip_specific_defaults.yaml"
    ```

=== "skip_specific_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/skip_specific_overrides.yaml"
    ```

Only `port` and `timeout` will be skipped if invalid; other fields still raise errors.

If a required field is invalid in all sources and has no default:

```
Config loading errors (1)

  [port]  Missing required field (invalid in: yaml 'defaults.yaml', yaml 'overrides.yaml')
   └── FILE 'defaults.yaml', line 3
       port: "not_a_number"
   └── FILE 'overrides.yaml', line 2
       port: "not_a_number_too"
```
