# Nested Resolve

Flat-key sources (ENV, `.env` file, Docker secrets) store nested dataclasses as either a single JSON string or as separate flat keys:

```
# JSON form
APP__DATABASE={"host": "db.example.com", "port": "5432"}

# Flat form
APP__DATABASE__HOST=db.example.com
APP__DATABASE__PORT=5432
```

When **both** forms are present for the same field, dature needs to know which one to use. This is what `nested_resolve_strategy` and `nested_resolve` control.

## The Problem

```python
--8<-- "examples/docs/advanced/nested_resolve/nested_resolve_problem.py"
```

By default, flat keys win (`nested_resolve_strategy="flat"`). This is usually what you want — flat keys are more specific and easier to override in CI/CD.

## Global Strategy

Set `nested_resolve_strategy` on `Source` to choose the source for **all** nested fields:

| Strategy | Behavior |
|----------|----------|
| `"flat"` (default) | Prefer flat keys (`APP__DATABASE__HOST`) over JSON |
| `"json"` | Prefer JSON value (`APP__DATABASE`) over flat keys |

!!! note
    The strategy only determines **priority** when both forms are present. If only one form exists, it is always used. For example, with `nested_resolve_strategy="flat"`, a JSON value `APP__DATABASE={"host": "x"}` will still be parsed normally when there are no flat keys like `APP__DATABASE__HOST`.

    ```python
    --8<-- "examples/docs/advanced/nested_resolve/nested_resolve_no_conflict.py"
    ```

=== "flat (default)"

    ```python
    --8<-- "examples/docs/advanced/nested_resolve/nested_resolve_global_flat.py"
    ```

=== "json"

    ```python
    --8<-- "examples/docs/advanced/nested_resolve/nested_resolve_global_json.py"
    ```

## Per-Field Strategy

Use `nested_resolve` to set different strategies for individual fields:

```python
--8<-- "examples/docs/advanced/nested_resolve/nested_resolve_per_field.py"
```

## Per-Field Overrides Global

When both `nested_resolve_strategy` and `nested_resolve` are set, per-field takes priority:

```python
--8<-- "examples/docs/advanced/nested_resolve/nested_resolve_override.py"
```

## All Flat-Key Sources

The mechanism works identically across all flat-key sources:

=== "ENV"

    ```python
    --8<-- "examples/docs/advanced/nested_resolve/nested_resolve_global_json.py"
    ```

=== ".env file"

    ```python
    --8<-- "examples/docs/advanced/nested_resolve/nested_resolve_envfile.py"
    ```

    ```env title="nested_resolve.env"
    --8<-- "examples/docs/advanced/nested_resolve/sources/nested_resolve.env"
    ```

=== "Docker secrets"

    ```python
    --8<-- "examples/docs/advanced/nested_resolve/nested_resolve_docker_secrets.py"
    ```

## Error Messages

When a conflict is resolved, error messages point to the **chosen** source. With `nested_resolve_strategy="json"`:

```
Config loading errors (1)

  [database.host]  Missing required field
   └── ENV 'APP__DATABASE' = '{"port": "5432"}'
```

With `nested_resolve_strategy="flat"`:

```
Config loading errors (1)

  [database.host]  Missing required field
   └── ENV 'APP__DATABASE__HOST'
```

## Deep Nesting

The strategy applies at the top-level field. For three-level nesting like `var.sub.key`, the conflict is detected on `var`:

```
APP__VAR={"sub": {"key": "from_json"}}
APP__VAR__SUB__KEY=from_flat
```

With `nested_resolve_strategy="flat"`, the flat key `APP__VAR__SUB__KEY` wins.
