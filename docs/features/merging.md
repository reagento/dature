# Merging

Load configuration from multiple sources and merge them into one dataclass.

## Basic Merging

Pass multiple `Source` objects to `dature.load()`:

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

## Multiple Sources

Multiple sources use `"last_wins"` by default:

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

| Strategy | Behavior |
|----------|----------|
| `"last_wins"` | Last source overrides (default) |
| `"first_wins"` | First source wins |
| `"first_found"` | Uses the first source that loads successfully, skips broken sources automatically |
| `"raise_on_conflict"` | Raises `MergeConflictError` if the same key appears in multiple sources with different values |

Nested dicts are merged recursively. Lists and scalars are replaced entirely according to the strategy.

=== "last_wins"

    Last source overrides earlier ones. This is the default strategy.

    ```python
    --8<-- "examples/docs/features/merging/merging_strategy_last_wins.py"
    ```

    === "common_defaults.yaml"

        ```yaml
        --8<-- "examples/docs/shared/common_defaults.yaml"
        ```

    === "common_overrides.yaml"

        ```yaml
        --8<-- "examples/docs/shared/common_overrides.yaml"
        ```

=== "first_wins"

    First source wins on conflict. Later sources only fill in missing keys.

    ```python
    --8<-- "examples/docs/features/merging/merging_strategy_first_wins.py"
    ```

    === "common_defaults.yaml"

        ```yaml
        --8<-- "examples/docs/shared/common_defaults.yaml"
        ```

    === "common_overrides.yaml"

        ```yaml
        --8<-- "examples/docs/shared/common_overrides.yaml"
        ```

=== "first_found"

    Uses the first source that loads successfully and ignores the rest. Broken sources (missing file, parse error) are skipped automatically — no `skip_if_broken` needed. Type errors (wrong type, missing field) are **not** skipped.

    ```python
    --8<-- "examples/docs/features/merging/merging_strategy_first_found.py"
    ```

    === "common_defaults.yaml"

        ```yaml
        --8<-- "examples/docs/shared/common_defaults.yaml"
        ```

=== "raise_on_conflict"

    Raises `MergeConflictError` if the same key appears in multiple sources with different values. Works best when sources have disjoint keys.

    ```python
    --8<-- "examples/docs/features/merging/merging_strategy_raise_on_conflict.py"
    ```

    === "common_raise_on_conflict_a.yaml"

        ```yaml
        --8<-- "examples/docs/shared/common_raise_on_conflict_a.yaml"
        ```

    === "common_raise_on_conflict_b.yaml"

        ```yaml
        --8<-- "examples/docs/shared/common_raise_on_conflict_b.yaml"
        ```

For per-field strategy overrides, see [Per-Field Merge Strategies](../advanced/merge-rules.md#per-field-merge-strategies). To enforce that related fields are always overridden together, see [Field Groups](../advanced/merge-rules.md#field-groups).

## Merge Parameters

All merge-related parameters are passed directly to `dature.load()` as keyword arguments:

| Parameter | Description |
|-----------|-------------|
| `strategy` | Global merge strategy. Default: `"last_wins"`. See [Merge Strategies](#merge-strategies) |
| `field_merges` | Per-field merge strategy overrides. See [Per-Field Merge Strategies](../advanced/merge-rules.md#per-field-merge-strategies) |
| `field_groups` | Enforce related fields are overridden together. See [Field Groups](../advanced/merge-rules.md#field-groups) |
| `skip_broken_sources` | Skip sources that fail to load. See [Skipping Broken Sources](../advanced/merge-rules.md#skipping-broken-sources) |
| `skip_invalid_fields` | Drop fields with invalid values. See [Skipping Invalid Fields](../advanced/merge-rules.md#skipping-invalid-fields) |
| `expand_env_vars` | ENV variable expansion mode. See [ENV Expansion](../advanced/env-expansion.md) |
| `secret_field_names` | Extra secret name patterns for masking. See [Masking](masking.md) |
| `mask_secrets` | Enable/disable secret masking for all sources. See [Masking](masking.md) |
| `nested_resolve_strategy` | Default priority when both JSON and flat keys exist: `"flat"` (default) or `"json"`. Applies to all sources. See [Nested Resolve](../advanced/nested-resolve.md) |
| `nested_resolve` | Default per-field strategy overrides for all sources. See [Nested Resolve](../advanced/nested-resolve.md#per-field-strategy) |
