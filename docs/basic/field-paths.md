# Field Paths

`F` is a type-safe factory for building field path references. It is used wherever dature needs to identify a specific dataclass field — explicit renaming, merge strategies, validation, field groups, and more.

## Syntax

Three forms are available:

```python
--8<-- "docs/examples/api_reference/api_reference_field_path.py"
```

| Form | Example | When to use |
|------|---------|-------------|
| Eager (class) | `F[Config].host` | Normal use when the class is already defined |
| Nested | `F[Config].database.host` | Multi-level nested dataclasses |
| String | `F["Config"].host` | Decorator mode — the class is not yet defined at import time |

Paths are validated eagerly: accessing a field that does not exist on the owner dataclass raises an `AttributeError` immediately rather than at load time.

## Where `F` is used

| Parameter | Used in |
|-----------|---------|
| `field_mapping` | `Source(field_mapping={F[C].field: "key"})` — rename a field in the source. See [Naming](naming.md#field_mapping). |
| `field_merges` | `load(..., field_merges={F[C].field: "append"})` — per-field merge strategy. See [Merge Strategies](../advanced/merge-strategies.md). |
| `field_groups` | `load(..., field_groups=[(F[C].a, F[C].b)])` — fields that must change together. See [Field Groups](../advanced/field-groups.md). |
| `validators` | `Source(validators={F[C].field: Gt(0)})` — per-field validators in source metadata. See [Validation](validation.md#metadata-validators). |
| `skip_field_if_invalid` | `Source(skip_field_if_invalid=F[C].field)` — drop a field silently on validation failure. See [Skip Behaviors](../advanced/skip-behaviors.md#skipping-invalid-fields). |
| `nested_resolve` | `Source(nested_resolve={F[C].field: "json"})` — per-field nested resolve strategy. See [Nested Resolve](../advanced/nested-resolve.md#per-field-strategy). |

## `F` vs `ref`

`F` and `ref` look similar but serve entirely different purposes:

- **`F[Config].field`** — identifies a *schema field* (compile-time). Used to configure dature's behavior for a specific field. Has no runtime value of its own.
- **`ref.tag.key`** / **`"${@tag.key}"`** — references a *value from another source* (runtime). Used for cross-source value interpolation. See [Cross-Source Refs](../advanced/cross_source_refs.md).

!!! tip
    Use `F` when configuring how dature handles a field (naming, merging, validation).
    Use `ref` when a source's value should depend on a value from another source.
