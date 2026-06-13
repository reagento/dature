# Merge Strategies

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
    --8<-- "docs/examples/advanced/merge_strategies/sources/merging_field_base.yaml"
    ```

=== "merging_field_override.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/merge_strategies/sources/merging_field_override.yaml"
    ```

Each strategy produces a different result:

=== "first_wins"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/merging_field_first_wins.py:example"
    ```

=== "last_wins"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/merging_field_last_wins.py:example"
    ```

=== "append"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/merging_field_append.py:example"
    ```

=== "append_unique"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/merging_field_append_unique.py:example"
    ```

=== "prepend"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/merging_field_prepend.py:example"
    ```

=== "prepend_unique"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/merging_field_prepend_unique.py:example"
    ```

Nested fields are supported — see [Field Paths](../basic/field-paths.md) for the full syntax.

### With `raise_on_conflict`

Fields with an explicit strategy are excluded from conflict detection:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/field_strategy_conflict.py:example"
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
    --8<-- "docs/examples/advanced/merge_strategies/field_strategy_callable.py:example"
    ```

=== "Class"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/field_strategy_custom.py:example"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_overrides.yaml"
    ```

---

## Custom Source Strategy

The global `strategy` parameter accepts not only the names from [Merge Strategies](../basic/merging.md#merge-strategies) but also any object implementing the public `SourceMergeStrategy` `Protocol`:

```python
--8<-- "src/dature/loading/merge_runtime.py:source-merge-strategy"
```

The strategy receives the raw `Source` instances (not pre-loaded data) and a `LoadCtx` helper. The primary API for applying a source to the running base is `ctx.merge(source=src, base=base, op=...)` — it loads the source (cached), runs the merge `op` (default `deep_merge_last_wins`), and registers the step so debug logs and `LoadReport.field_origins` are populated correctly. A minimal custom strategy is one loop (as example of SourceLastWins):

```python
--8<-- "src/dature/strategies/source.py:source-last-wins-strategy"
```

Override `op` to plug in your own merge function — e.g. shallow overlay for env on top of files:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/merge_strategies/source_strategy_custom.py:example"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_overrides.yaml"
    ```

`isinstance(src, EnvSource)` (or any other concrete `Source` subclass) lets the strategy dispatch on source type — useful when env variables should override file content rather than merge with it. Pass `skip_on_error=True` to `ctx.merge(...)` (or `ctx.load(...)`) if you want broken sources to be skipped silently regardless of `skip_if_broken` (this is what `SourceFirstFound` does internally).

`ctx.merge` is the single hook — once your strategy funnels every per-source step through it, debug logs (`[Cls] Merge step N ...`, `State after step N: ...`) and `LoadReport.field_origins` are populated automatically; there's no separate registration call to remember.
