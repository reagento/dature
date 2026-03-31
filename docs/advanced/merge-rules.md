# Merge Rules

## How Merging Works

```mermaid
graph TD
    A[Source 1: defaults.yaml] --> D[Load & Parse]
    B[Source 2: overrides.yaml] --> E[Load & Parse]
    C[Source 3: ENV vars] --> F[Load & Parse]
    D --> G[Raw Dict 1]
    E --> H[Raw Dict 2]
    F --> I[Raw Dict 3]
    G --> J{Merge Strategy}
    H --> J
    I --> J
    J --> K[Merged Dict]
    K --> L[Type Conversion]
    L --> M[Validation]
    M --> N[Dataclass Instance]
```

## Per-Field Merge Strategies

Override the global strategy for individual fields using `field_merges`.

Available field merge strategies:

| Strategy | Behavior |
|----------|----------|
| `"first_wins"` | Keep the value from the first source |
| `"last_wins"` | Keep the value from the last source |
| `"append"` | Concatenate lists: `base + override` |
| `"append_unique"` | Concatenate lists, removing duplicates |
| `"prepend"` | Concatenate lists: `override + base` |
| `"prepend_unique"` | Concatenate lists in reverse order, removing duplicates |

Given two sources with overlapping `tags`:

=== "merging_field_base.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/merge_rules/sources/merging_field_base.yaml"
    ```

=== "merging_field_override.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/merge_rules/sources/merging_field_override.yaml"
    ```

Each strategy produces a different result:

=== "first_wins"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_field_first_wins.py"
    ```

=== "last_wins"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_field_last_wins.py"
    ```

=== "append"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_field_append.py"
    ```

=== "append_unique"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_field_append_unique.py"
    ```

=== "prepend"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_field_prepend.py"
    ```

=== "prepend_unique"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_field_prepend_unique.py"
    ```

Nested fields are supported: `dature.F[Config].database.host`.

Per-field strategies work with `"raise_on_conflict"` — fields with an explicit strategy are excluded from conflict detection.

## With raise_on_conflict

Fields with an explicit strategy are excluded from conflict detection:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/advanced_merge_rules_conflict.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_overrides.yaml"
    ```

## Callable Merge

You can also pass a callable as the strategy:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/advanced_merge_rules_callable.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_overrides.yaml"
    ```

The callable receives a `list[JSONValue]` (one value per source) and returns the merged value.

## Skipping Broken Sources

Skip sources that fail to load (missing file, invalid syntax):

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_skip_broken.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_defaults.yaml"
    ```

Override per source with `skip_if_broken` on `Source` (takes priority over the global flag):

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_skip_broken_per_source.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_defaults.yaml"
    ```

If all sources fail to load, a `ValueError` is raised.

## Skipping Invalid Fields

Drop fields with invalid values and let other sources or defaults fill them in:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_skip_invalid.py"
    ```

=== "merging_skip_invalid_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/merge_rules/sources/merging_skip_invalid_defaults.yaml"
    ```

Restrict skipping to specific fields:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/merge_rules/merging_skip_invalid_per_field.py"
    ```

=== "merging_skip_invalid_per_field_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/merge_rules/sources/merging_skip_invalid_per_field_defaults.yaml"
    ```

=== "merging_skip_invalid_per_field_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/merge_rules/sources/merging_skip_invalid_per_field_overrides.yaml"
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
