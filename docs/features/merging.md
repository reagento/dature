# Merging

Load configuration from multiple sources and merge them into one dataclass.

## Basic Merging

Use `MergeMetadata` to combine sources:

=== "Python"

    ```python
    --8<-- "examples/docs/features/merging/merging_basic.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_overrides.yaml"
    ```

## Tuple Shorthand

Pass a tuple of `LoadMetadata` directly — uses `LAST_WINS` by default:

=== "Python"

    ```python
    --8<-- "examples/docs/features/merging/merging_tuple_shorthand.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_overrides.yaml"
    ```

Works as a decorator too:

=== "Python"

    ```python
    --8<-- "examples/docs/features/merging/merging_tuple_shorthand_decorator.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_defaults.yaml"
    ```

## Merge Strategies

=== "Python"

    ```python
    --8<-- "examples/docs/features/merging/merging_strategies.py"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_overrides.yaml"
    ```

| Strategy | Behavior |
|----------|----------|
| `LAST_WINS` | Last source overrides (default) |
| `FIRST_WINS` | First source wins |
| `RAISE_ON_CONFLICT` | Raises `MergeConflictError` if the same key appears in multiple sources with different values |

Nested dicts are merged recursively. Lists and scalars are replaced entirely according to the strategy.

For per-field strategy overrides, see [Per-Field Merge Strategies](../advanced/merge-rules.md#per-field-merge-strategies). To enforce that related fields are always overridden together, see [Field Groups](../advanced/merge-rules.md#field-groups).

## MergeMetadata Reference

```python
--8<-- "src/dature/metadata.py:merge-metadata"
```

| Parameter | Description |
|-----------|-------------|
| `sources` | Tuple of `LoadMetadata` descriptors — one per source to merge |
| `strategy` | Global merge strategy. Default: `LAST_WINS`. See [Merge Strategies](#merge-strategies) |
| `field_merges` | Per-field merge strategy overrides. See [Per-Field Merge Strategies](../advanced/merge-rules.md#per-field-merge-strategies) |
| `field_groups` | Enforce related fields are overridden together. See [Field Groups](../advanced/merge-rules.md#field-groups) |
| `skip_broken_sources` | Skip sources that fail to load. See [Skipping Broken Sources](../advanced/merge-rules.md#skipping-broken-sources) |
| `skip_invalid_fields` | Drop fields with invalid values. See [Skipping Invalid Fields](../advanced/merge-rules.md#skipping-invalid-fields) |
| `expand_env_vars` | ENV variable expansion mode. See [ENV Expansion](../advanced/env-expansion.md) |
| `secret_field_names` | Extra secret name patterns for masking. See [Masking](masking.md) |
| `mask_secrets` | Enable/disable secret masking for all sources. See [Masking](masking.md) |
