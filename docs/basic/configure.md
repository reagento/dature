# Configure

## The Dature instance

`dature.Dature(...)` is the recommended way to customize loading behaviour.
Each instance is **immutable** and **independent** — creating a new one does not affect others.
All option groups merge on top of the `DATURE_*` environment defaults: omit a group to inherit the env value, pass `{}` to reset it to built-in defaults, or pass individual fields to override them.

=== "Dature instance"

    ```python
    --8<-- "docs/examples/basic/configure/advanced_configure.py:example"
    ```

=== "Environment + instance override"

    ```python
    --8<-- "docs/examples/basic/configure/advanced_configure_env_runtime_override.py:example"
    ```

=== "common_app.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_app.yaml"
    ```

### Decorator mode

`conf.load(source)` used as a decorator binds the config at **decoration time** (module import), not lazily on each call.
If you need config determined at call time, use function mode (`conf.load(source, schema=MyClass)`) inside the function body.

```python
--8<-- "docs/examples/basic/configure/decorator_mode.py:example"
```

### MaskingConfig

```python
--8<-- "src/dature/config.py:masking-config"
```

### ErrorDisplayConfig

```python
--8<-- "src/dature/config.py:error-display-config"
```

Controls how much source context error messages show. Env sets the process-wide default; override it
per instance the same way as any other group — two instances loading the same broken config render the
failure differently:

```python
--8<-- "docs/examples/basic/configure/error_display_configure.py:example"
```

### LoadingConfig

```python
--8<-- "src/dature/config.py:loading-config"
```

### type_loaders

Register instance-level custom type loaders that apply to all loads through that instance.
Priority: `Dature` < load-level < source. See [Custom Types & Loaders](../advanced/custom_types.md#per-source-vs-global).

!!! warning "configure() is deprecated"
    `dature.configure()` is deprecated since **1.3** and will be removed in **1.5**.
    Migrate to `dature.Dature(...)` — the same option groups are accepted.

    ```python
    # Before
    --8<-- "docs/examples/basic/configure/configure_migration.py:before"
    ```

    ```python
    # After
    --8<-- "docs/examples/basic/configure/configure_migration.py:after"
    ```

## Environment Variables

dature auto-loads its own config from `DATURE_*` environment variables on first use. Nested fields use `__` as delimiter:

| Variable | Config | Field | Description |
|---|---|---|---|
| `DATURE_MASKING__MASK` | [MaskingConfig](#maskingconfig) | `mask` | Replacement string for masked values |
| `DATURE_MASKING__VISIBLE_PREFIX` | [MaskingConfig](#maskingconfig) | `visible_prefix` | Number of characters left visible at the start |
| `DATURE_MASKING__VISIBLE_SUFFIX` | [MaskingConfig](#maskingconfig) | `visible_suffix` | Number of characters left visible at the end |
| `DATURE_MASKING__MIN_HEURISTIC_LENGTH` | [MaskingConfig](#maskingconfig) | `min_heuristic_length` | Minimum field value length for auto-detection of secrets by field name |
| `DATURE_MASKING__HEURISTIC_THRESHOLD` | [MaskingConfig](#maskingconfig) | `heuristic_threshold` | Uncommon bigram ratio threshold for heuristic secret detection (0.0–1.0) |
| `DATURE_MASKING__MASKING_MODE` | [MaskingConfig](#maskingconfig) | `masking_mode` | Masking aggressiveness: `all` (default, mask every string value), `secrets_only` (mask only fields matched by name/type/heuristic), or `none` |
| `DATURE_ERROR_DISPLAY__MAX_VISIBLE_LINES` | [ErrorDisplayConfig](#errordisplayconfig) | `max_visible_lines` | Max lines shown in error messages for source file previews |
| `DATURE_ERROR_DISPLAY__MAX_LINE_LENGTH` | [ErrorDisplayConfig](#errordisplayconfig) | `max_line_length` | Max character width per line in error messages |
| `DATURE_LOADING__CACHE` | [LoadingConfig](#loadingconfig) | `cache` | Enable caching. `true`/`false` or a `timedelta` string (e.g. `0:00:30`, `30 seconds`) for TTL. See [Caching](../advanced/caching.md) |
| `DATURE_LOADING__CACHE_ENGINE` | [LoadingConfig](#loadingconfig) | `cache_engine` | Retain the compiled engine across loads, independent of `cache`. See [Caching](../advanced/caching.md#cache_engine-retaining-the-compiled-engine) |
| `DATURE_LOADING__STALE_ON_ERROR` | [LoadingConfig](#loadingconfig) | `stale_on_error` | What to do when a cached reload fails: `keep` (default), `retry`, or `raise`. See [Caching](../advanced/caching.md#stale_on_error-keeping-the-last-good-config) |
| `DATURE_LOADING__DEBUG` | [LoadingConfig](#loadingconfig) | `debug` | Attach `LoadReport` to every loaded instance |
| `DATURE_LOADING__NESTED_RESOLVE_STRATEGY` | [LoadingConfig](#loadingconfig) | `nested_resolve_strategy` | Default priority for JSON vs flat keys: `flat` (default) or `json`. See [Nested Resolve](../advanced/nested-resolve.md) |
| `DATURE_LOADING__EXPAND_ENV_VARS` | [LoadingConfig](#loadingconfig) | `expand_env_vars` | Default env var expansion mode: `default`, `disabled`, `empty`, or `strict`. See [Env Expansion](../advanced/env-expansion.md) |
| `DATURE_LOADING__SEARCH_SYSTEM_PATHS` | [LoadingConfig](#loadingconfig) | `search_system_paths` | Enable automatic config file search in standard system locations (`~/.config/`, `/etc/`, `%APPDATA%/`). See [Config Search](../advanced/config-search.md) |
| `DATURE_LOADING__SYSTEM_CONFIG_DIRS` | [LoadingConfig](#loadingconfig) | `system_config_dirs` | Custom colon-separated list of directories for config file search (overrides auto-detection) |
