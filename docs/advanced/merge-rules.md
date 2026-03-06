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

## Callable Merge

You can also pass a callable as the strategy:

```python
MergeRule(
    F[Config].tags,
    lambda values: sorted(set(v for lst in values for v in lst)),
)
```

The callable receives a `list[JSONValue]` (one value per source) and returns the merged value.
