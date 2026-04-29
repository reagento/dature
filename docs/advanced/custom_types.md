# Custom Types & Loaders

## Custom Types

Use `type_loaders` to teach dature how to parse custom types from strings.

Pass `type_loaders` as a `dict[type, Callable]` mapping types to conversion functions:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced/custom_types/custom_type.py"
    ```

=== "custom_type_common.yaml"

    ```yaml
    --8<-- "examples/docs/advanced/custom_types/sources/custom_type_common.yaml"
    ```

### Per-source vs Global

`type_loaders` can be set per-source in `Source`, in `dature.load()` for merge mode, or globally via `configure()`:

=== "Per-source (Source)"

    ```python
    --8<-- "examples/docs/advanced/custom_types/custom_type.py"
    ```

=== "Per-merge (load)"

    ```python
    --8<-- "examples/docs/advanced/custom_types/custom_type_merge.py"
    ```

=== "Global (configure)"

    ```python
    --8<-- "examples/docs/advanced/custom_types/advanced_configure_type_loaders.py"
    ```

When both per-source and global `type_loaders` are set, they merge — per-source loaders take priority.

## Custom Source Classes

For formats that dature doesn't support out of the box, you can create your own source by subclassing one of the base classes from `dature.sources.base`:

### Choosing a base class

| Base class | Use when | You implement | You get for free |
|------------|----------|---------------|------------------|
| [`Source`](../api-reference.md#source) | Non-file data (API, database, custom protocol) | `format_name`, `_load() -> JSONValue` | Prefix filtering, env var expansion, type coercion, validation, merge support |
| [`FileSource`](../api-reference.md#filesourcesource) | File-based format (XML, CSV, HCL, …) | `format_name`, `_load_file(path: FileOrStream) -> JSONValue` | Everything from `Source` + `file` parameter, stream support, `file_display()`, `file_path_for_errors()`, `__repr__` |
| [`FlatKeySource`](../api-reference.md#flatkeysourcesource) | Flat key=value data (custom env store, Consul KV, …) | `format_name`, `_load() -> JSONValue` (flat `dict[str, str]`) | Everything from `Source` + `nested_sep` nesting, `nested_resolve`, automatic string→type parsing (`int`, `bool`, `date`, …) |

All base classes are in `dature.sources.base`:

```python
--8<-- "examples/docs/advanced/custom_types/custom_source_import.py"
```

### Minimal interface

Every custom source needs:

1. **`format_name`** — class-level string shown in `__repr__` and error messages (e.g. `"xml"`, `"consul"`)
2. **A load method** — `_load()` for `Source`/`FlatKeySource`, or `_load_file(path)` for `FileSource`. Must return `JSONValue` (a nested dict).

### Optional overrides

| Method | Default | Override when |
|--------|---------|---------------|
| `additional_loaders()` | `[]` (FileSource) or string-value loaders (FlatKeySource) | Your format stores all values as strings and needs extra type parsers (e.g. `bool`, `float`). |
| `file_display()` | `None` | Your source has a meaningful display path (shown in logs and errors). |
| `file_path_for_errors()` | `None` | Your source points to a file on disk (used in error messages). |
| `resolve_location(...)` | Empty `SourceLocation` | You want errors to show line numbers or variable names from your source. |
| `location_label` | inherited | Change the label in error messages (e.g. `"FILE"`, `"ENV"`, `"API"`). |

### Example: FileSource subclass

The most common case — reading a file format:

```python
--8<-- "examples/docs/advanced/custom_types/custom_loader.py"
```

```xml title="custom_loader.xml"
--8<-- "examples/docs/advanced/custom_types/sources/custom_loader.xml"
```

`FileSource` handles the `file` parameter, path expansion, and stream detection. Your `_load_file()` receives a `Path` or file-like object and returns a dict.

### Example: Source subclass (non-file)

For sources that don't read files — e.g. an API, a database, or an in-memory dict:

```python
--8<-- "examples/docs/advanced/custom_types/custom_dict_source.py"
```

### Tips

- All built-in features (type coercion, validation, prefix extraction, ENV expansion, merge support) work automatically with any custom source.
- Override `additional_loaders()` to return `string_value_loaders()` from `dature.sources.retort` if your format stores everything as strings (like INI or ENV).
- Pass your custom source to `dature.load()` the same way as any built-in source.
