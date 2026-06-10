# Field Groups

Ensure related fields are always overridden together:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/field_groups/field_groups_basic.py:setup"
    --8<-- "docs/examples/advanced/field_groups/field_groups_basic.py:example"
    ```

=== "common_field_groups_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_field_groups_defaults.yaml"
    ```

=== "common_field_groups_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_field_groups_overrides.yaml"
    ```

If `overrides.yaml` changes `host` and `port` together, the group constraint is satisfied. If a source partially overrides a group, `FieldGroupError` is raised:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_nested_error.py:setup"
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_nested_error.py:example"
    ```

=== "common_field_groups_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_field_groups_defaults.yaml"
    ```

=== "field_groups_partial_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/field_groups/sources/field_groups_partial_overrides.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_nested_error.stderr"
    ```

## Nested Dataclass Expansion

Passing a dataclass field expands it into all its leaf fields:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_expansion_error.py:setup"
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_expansion_error.py:example"
    ```

=== "field_groups_nested_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/field_groups/sources/field_groups_nested_defaults.yaml"
    ```

=== "advanced_field_groups_expansion_error_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/field_groups/sources/advanced_field_groups_expansion_error_overrides.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_expansion_error.stderr"
    ```

## Multiple Groups

If a source partially overrides multiple groups, all violations are reported:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_multiple_error.py:setup"
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_multiple_error.py:example"
    ```

=== "common_field_groups_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_field_groups_defaults.yaml"
    ```

=== "advanced_field_groups_multiple_error_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/field_groups/sources/advanced_field_groups_multiple_error_overrides.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/advanced/field_groups/advanced_field_groups_multiple_error.stderr"
    ```

Field groups work with all merge strategies and can be combined with `field_merges`.


