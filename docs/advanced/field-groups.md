# Field Groups

Ensure related fields are always overridden together. If a source partially overrides a group, `FieldGroupError` is raised:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/field_groups/advanced_field_groups_nested_error.py"
    ```

=== "common_field_groups_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_field_groups_defaults.yaml"
    ```

=== "field_groups_partial_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/field_groups/sources/field_groups_partial_overrides.yaml"
    ```

## Nested Dataclass Expansion

Passing a dataclass field expands it into all its leaf fields:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/field_groups/advanced_field_groups_expansion_error.py"
    ```

=== "field_groups_nested_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/field_groups/sources/field_groups_nested_defaults.yaml"
    ```

=== "advanced_field_groups_expansion_error_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/field_groups/sources/advanced_field_groups_expansion_error_overrides.yaml"
    ```

## Multiple Groups

If a source partially overrides multiple groups, all violations are reported:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/field_groups/advanced_field_groups_multiple_error.py"
    ```

=== "common_field_groups_defaults.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_field_groups_defaults.yaml"
    ```

=== "advanced_field_groups_multiple_error_overrides.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/field_groups/sources/advanced_field_groups_multiple_error_overrides.yaml"
    ```

Field groups work with all merge strategies and can be combined with `field_merges`.
