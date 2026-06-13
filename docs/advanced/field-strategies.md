# Field Strategies

## Per-Field Merge Strategies

Override the global strategy for individual fields using `field_merges`. Each value can be one of the built-in strategy names below, or any [callable or custom class](#custom-field-strategy) implementing `FieldMergeStrategy`.

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
    --8<-- "docs/examples/advanced/field_strategies/sources/merging_field_base.yaml"
    ```

=== "merging_field_override.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/field_strategies/sources/merging_field_override.yaml"
    ```

Each strategy produces a different result:

=== "first_wins"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/merging_field_first_wins.py:example"
    ```

=== "last_wins"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/merging_field_last_wins.py:example"
    ```

=== "append"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/merging_field_append.py:example"
    ```

=== "append_unique"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/merging_field_append_unique.py:example"
    ```

=== "prepend"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/merging_field_prepend.py:example"
    ```

=== "prepend_unique"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/merging_field_prepend_unique.py:example"
    ```

Nested fields are supported: `dature.F[Config].database.host`.

### With `raise_on_conflict`

Fields with an explicit strategy are excluded from conflict detection:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/field_strategy_conflict.py:example"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_overrides.yaml"
    ```

## Custom Field Strategy

### The `FieldMergeStrategy` Protocol

Any callable that takes a `list[JSONValue]` (one value per source) and returns the merged value satisfies the public `FieldMergeStrategy` `Protocol`:

```python
--8<-- "src/dature/strategies/field.py:field-merge-strategy"
```

The built-in field strategies are also exposed as classes from `dature.strategies.field`: `FieldFirstWins`, `FieldLastWins`, `FieldAppend`, `FieldAppendUnique`, `FieldPrepend`, `FieldPrependUnique`. They satisfy the same `Protocol`, so you can pass them directly to `field_merges` or compose them inside your own strategy.

### Examples

Pick a plain function for one-off logic, or a class for a named, reusable reducer:

=== "Function"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/field_strategy_callable.py:example"
    ```

=== "Class"

    ```python
    --8<-- "docs/examples/advanced/field_strategies/field_strategy_custom.py:example"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_overrides.yaml"
    ```
