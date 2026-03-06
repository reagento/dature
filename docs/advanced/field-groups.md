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

```python
@dataclass
class Database:
    host: str
    port: int

@dataclass
class Config:
    database: Database
    timeout: int

# FieldGroup(F[Config].database, F[Config].timeout)
# expands to (database.host, database.port, timeout)
```

## Multiple Groups

Multiple groups can be defined independently:

```python
field_groups=(
    FieldGroup(F[Config].host, F[Config].port),
    FieldGroup(F[Config].user, F[Config].password),
)
```

Field groups work with all merge strategies and can be combined with `field_merges`.
