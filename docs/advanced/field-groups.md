# Field Groups

Ensure related fields are always overridden together:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_field_groups_nested.py"
    ```

=== "field_groups_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/field_groups_defaults.yaml"
    ```

=== "field_groups_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/field_groups_overrides.yaml"
    ```

## Nested Dataclass Expansion

Passing a dataclass field expands it into all its leaf fields:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_field_groups_expansion.py"
    ```

=== "field_groups_nested_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/field_groups_nested_defaults.yaml"
    ```

=== "field_groups_nested_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/field_groups_nested_overrides.yaml"
    ```

## Multiple Groups

Multiple groups can be defined independently:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_field_groups_multiple.py"
    ```

=== "field_groups_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/field_groups_defaults.yaml"
    ```

=== "field_groups_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/field_groups_overrides.yaml"
    ```

Field groups work with all merge strategies and can be combined with `field_merges`.

## Partial Override Error

If a source changes some fields in a group but not others, `FieldGroupError` is raised:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_field_groups_error.py"
    ```

=== "field_groups_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/sources/field_groups_defaults.yaml"
    ```

=== "field_groups_partial_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/sources/field_groups_partial_overrides.yaml"
    ```
