# Loading

## How Single-Source Loading Works

```mermaid
graph TD
    S[Source] --> L[Load raw data]
    L --> R[Raw Dict]
    R --> PB{skip_invalid_fields?}
    PB -- yes --> PR["field_pass(skip=True): drop fields\nthat fail coercion or validation"]
    PB -- no --> CF[Coerce flag fields]
    PR --> CF
    CF --> V{Source has field validators?}
    V -- yes --> FP["field_pass: run Annotated + source.validators\non provided fields only"]
    V -- no --> FR
    FP --> FR["root_retort: final construction + root_validators"]
    FR --> FB["Fallback: validate Annotated fields\nthat no source provided"]
    FB --> D[Dataclass]
```

**`field_pass`** runs validators only on fields the source actually provided — absent fields stay
`NOT_LOADED` and are skipped. When `skip_invalid_fields=True`, `field_pass(skip=True)` silently
drops fields that fail coercion **or** a field validator instead of raising.

**`root_retort`** performs final type coercion and fires any `root_validators=` passed to `load()`
/ `Loader` once the dataclass is fully constructed.

For multi-source loading, see [Merging](basic/merging.md).

---

When a `dature.load(...)` call fails, the error message tells you which field
broke, where in the source it came from, and why. This page walks through the
failures you are most likely to hit while wiring up your first config — and one
pattern for recovering from them.

All examples share the same schema

## Source does not exist

Wrong path or wrong working directory — the most common first error. dature
raises a plain `FileNotFoundError` before any parsing happens.

=== "Python"

    ```python
    --8<-- "docs/examples/loading/loading_missing_file.py:example"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/loading/loading_missing_file.stderr"
    ```

## Source exists but is broken

The file is present but the parser can't read it (here: invalid YAML
indentation). dature does not swallow parser errors — the underlying exception
propagates with the original file and line.

=== "Python"

    ```python
    --8<-- "docs/examples/loading/loading_broken_file.py:example"
    ```

=== "broken.yaml"

    ```yaml
    --8<-- "docs/examples/loading/sources/broken.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/loading/loading_broken_file.stderr"
    ```

## Type mismatch

The source parses, but a value can't be coerced to the field's annotated type.
dature raises a `FieldLoadError` with the field path, the offending value, a
caret pointing at it, and the source location.

=== "Python"

    ```python
    --8<-- "docs/examples/loading/loading_type_mismatch.py:example"
    ```

=== "type_mismatch.yaml"

    ```yaml
    --8<-- "docs/examples/loading/sources/type_mismatch.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/loading/loading_type_mismatch.stderr"
    ```

## Required field missing

A field with no default value is absent from the source. The error points at
the file but has no line — there is nothing in the source to highlight.

=== "Python"

    ```python
    --8<-- "docs/examples/loading/loading_missing_field.py:example"
    ```

=== "missing_field.yaml"

    ```yaml
    --8<-- "docs/examples/loading/sources/missing_field.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/loading/loading_missing_field.stderr"
    ```

## Multiple errors at once

dature does not stop at the first error — it keeps going and reports every
failed field together as an `ExceptionGroup`. You fix the config in one pass
instead of "fix, rerun, fix, rerun".

=== "Python"

    ```python
    --8<-- "docs/examples/loading/loading_multiple_errors.py:example"
    ```

=== "multiple_errors.yaml"

    ```yaml
    --8<-- "docs/examples/loading/sources/multiple_errors.yaml"
    ```

=== "Error"

    ```
    --8<-- "docs/examples/loading/loading_multiple_errors.stderr"
    ```

## Recovering: skip an unavailable source

When merging multiple sources, an absent or malformed one can be skipped so the
next source supplies the values. Use `skip_if_missing=True` for files that may
not exist, or `skip_if_broken=True` for files that exist but may be malformed:

=== "Python"

    ```python
    --8<-- "docs/examples/loading/loading_skip_broken.py:example"
    ```

=== "fallback.yaml"

    ```yaml
    --8<-- "docs/examples/loading/sources/fallback.yaml"
    ```

If **every** source fails, dature still raises — there is no value to load.
See [Skipping Sources with Parse Errors](advanced/skip-behaviors.md#skipping-sources-with-parse-errors)
and [Skipping Missing Sources](advanced/skip-behaviors.md#skipping-missing-sources) for the full picture,
including per-source overrides and `skip_invalid_fields`.

