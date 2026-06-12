# Loading

When a `dature.load(...)` call fails, the error message tells you which field
broke, where in the source it came from, and why. This page walks through the
failures you are most likely to hit while wiring up your first config — and one
pattern for recovering from them.

All examples share the same schema

## Source does not exist

Wrong path or wrong working directory — the most common first error. dature
raises a plain `FileNotFoundError` before any parsing happens.

```python title="Code"
--8<-- "docs/examples/loading/loading_missing_file.py:included"
```

``` title="Error"
--8<-- "docs/examples/loading/loading_missing_file.stderr"
```

## Source exists but is broken

The file is present but the parser can't read it (here: invalid YAML
indentation). dature does not swallow parser errors — the underlying exception
propagates with the original file and line.

```yaml title="broken.yaml"
--8<-- "docs/examples/loading/sources/broken.yaml"
```

```python title="Code"
--8<-- "docs/examples/loading/loading_broken_file.py:included"
```

``` title="Error"
--8<-- "docs/examples/loading/loading_broken_file.stderr"
```

## Type mismatch

The source parses, but a value can't be coerced to the field's annotated type.
dature raises a `FieldLoadError` with the field path, the offending value, a
caret pointing at it, and the source location.

```yaml title="type_mismatch.yaml"
--8<-- "docs/examples/loading/sources/type_mismatch.yaml"
```

```python title="Code"
--8<-- "docs/examples/loading/loading_type_mismatch.py:included"
```

``` title="Error"
--8<-- "docs/examples/loading/loading_type_mismatch.stderr"
```

## Required field missing

A field with no default value is absent from the source. The error points at
the file but has no line — there is nothing in the source to highlight.

```yaml title="missing_field.yaml"
--8<-- "docs/examples/loading/sources/missing_field.yaml"
```

```python title="Code"
--8<-- "docs/examples/loading/loading_missing_field.py:included"
```

``` title="Error"
--8<-- "docs/examples/loading/loading_missing_field.stderr"
```

## Multiple errors at once

dature does not stop at the first error — it keeps going and reports every
failed field together as an `ExceptionGroup`. You fix the config in one pass
instead of "fix, rerun, fix, rerun".

```yaml title="multiple_errors.yaml"
--8<-- "docs/examples/loading/sources/multiple_errors.yaml"
```

```python title="Code"
--8<-- "docs/examples/loading/loading_multiple_errors.py:included"
```

``` title="Error"
--8<-- "docs/examples/loading/loading_multiple_errors.stderr"
```

## Recovering: skip a broken source

When merging multiple sources, a missing or malformed one can be skipped with
`skip_if_broken=True` so the next source supplies the values:

```yaml title="fallback.yaml"
--8<-- "docs/examples/loading/sources/fallback.yaml"
```

```python title="Code"
--8<-- "docs/examples/loading/loading_skip_broken.py:included"
```

If **every** source fails, dature still raises — there is no value to load. The
flag also has variants for skipping individual invalid fields rather than
entire sources. See [Merge Rules — Skipping Broken Sources](advanced/merge-rules.md#skipping-broken-sources)
for the full picture.

## What's next

- [Validation](features/validation.md) — add custom rules so loading also
  fails when values are *the wrong shape* (out of range, bad regex, …), not
  just the wrong type.
- [Merge Rules](advanced/merge-rules.md) — control what happens when several
  sources disagree, and how to skip broken or invalid pieces.
- [Debug & Reports](advanced/debug.md) — inspect what each source contributed
  before the merge happened.
