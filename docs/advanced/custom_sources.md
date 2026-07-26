# Custom Source Classes

For formats that dature doesn't support out of the box, you can create your own source by subclassing one of the base classes from `dature.sources.base`:

## Choosing a base class

| Base class | Use when | You implement | You get for free |
|------------|----------|---------------|------------------|
| [`Source`](../api-reference.md#source) | Non-file data (API, database, custom protocol) | `format_name`, `_load() -> JSONValue` | Prefix filtering, env var expansion, type coercion, validation, merge support |
| [`FileSource`](../api-reference.md#filesourcesource) | File-based format (XML, CSV, HCL, …) | `format_name`, `_load_file(path: FileOrStream) -> JSONValue` | Everything from `Source` + `file` parameter, stream support, `file_display()`, `file_path_for_errors()`, `__repr__` |
| [`FlatKeySource`](../api-reference.md#flatkeysourcesource) | Flat key=value data (custom env store, Consul KV, …) | `format_name`, `_load() -> JSONValue` (flat `dict[str, str]`) | Everything from `Source` + `nested_sep` nesting, `nested_resolve`, automatic string→type parsing (`int`, `bool`, `date`, …) |
| [`RemoteSource`](../api-reference.md#remotesource) | Network/remote data (AWS Secrets Manager, Consul, Kubernetes, …) | `format_name`, `remote_address() -> str`, `_fetch() -> JSONValue` | Everything from `Source` + `display_name()`, `file_display()`, `location_label = "REMOTE"` |

All base classes are in `dature.sources.base`:

```python
--8<-- "docs/examples/advanced/custom_sources/custom_source_import.py"
```

## Minimal interface

Every custom source needs:

1. **`format_name`** — class-level string shown in `__repr__` and error messages (e.g. `"xml"`, `"consul"`)
2. **A load method** — `_load()` for `Source`/`FlatKeySource`, or `_load_file(path)` for `FileSource`. Must return `JSONValue` (a nested dict).

## Optional overrides

| Method | Default | Override when |
|--------|---------|---------------|
| `format_loaders()` | `[]` (FileSource) or string-value loaders (FlatKeySource) | Your format stores all values as strings and needs extra type parsers (e.g. `bool`, `float`). |
| `_build_line_index(content)` | `None` (no diagnostics) | You want errors to show exact line numbers from your source. Return a `dict[tuple[str, ...], LineRange]` mapping dotted key paths to line ranges. See `sources/yaml_.py` as reference. |
| `file_display()` | `None` | Your source has a meaningful display path (shown in logs and errors). |
| `file_path_for_errors()` | `None` | Your source points to a file on disk (used in error messages). |
| `resolve_location(...)` | Uses `_build_line_index` + caret computation | Low-level escape hatch — override only when `_build_line_index` is not enough (e.g. env var name in error messages). |
| `location_label` | inherited | Change the label in error messages (e.g. `"FILE"`, `"ENV"`, `"API"`). |

## Example: FileSource subclass

The most common case — reading a file format:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/custom_sources/custom_loader.py:example"
    ```

=== "custom_loader.xml"

    ```xml title="custom_loader.xml"
    --8<-- "docs/examples/advanced/custom_sources/sources/custom_loader.xml"
    ```

`FileSource` handles the `file` parameter, path expansion, and stream detection. Your `_load_file()` receives a `Path` or file-like object and returns a dict.

## Example: Source subclass (non-file)

For sources that don't read files — e.g. an API, a database, or an in-memory dict:

```python
--8<-- "docs/examples/advanced/custom_sources/custom_dict_source.py"
```

## Protocol-based sources

Subclassing `Source` is the recommended path — you get all the shared behaviour for free. But dature's loader uses *structural typing*: it checks `isinstance(source, SourceProtocol)`, not `issubclass(MySource, Source)`. Any `@dataclass` that implements the full `SourceProtocol` interface is accepted, without inheriting from `Source`.

```python
from dature.sources.protocol import SourceProtocol, FileSourceProtocol
```

`SourceProtocol` (in `dature.sources.protocol`) is the complete interface the loader requires — class-level attributes (`format_name`, `location_label`, `config_group`), instance fields (`prefix`, `tag`, `when`, …), and methods (`load_raw()`, `display_name()`, `resolve_location()`, …).

`FileSourceProtocol` is the narrower interface for sources that point to a file on disk. If your source implements it (exposes `skip_if_broken`, `skip_if_missing`, `file_path_for_errors()`, `encoding_for_errors()`), the loading machinery will use these for per-source skip behaviour and error enrichment automatically.

!!! tip
    Implementing `SourceProtocol` from scratch is verbose — you'd replicate most of what `Source` already provides. Consider this path only when you have an existing class hierarchy that can't inherit from `Source`. For every other case, subclass `Source`, `FileSource`, or `FlatKeySource` as shown above.

## Tips

- All built-in features (type coercion, validation, prefix extraction, ENV expansion, merge support) work automatically with any custom source.
- Override `format_loaders()` to return `string_value_loaders()` from `dature.sources.base` if your format stores everything as strings (like INI or ENV).
- Pass your custom source to `dature.load()` the same way as any built-in source.
