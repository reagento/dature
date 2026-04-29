# Configure

## Global configure()

Customize defaults for the entire application — programmatically or via environment variables:

=== "configure()"

    ```python
    --8<-- "examples/docs/features/configure/advanced_configure.py"
    ```

=== "Environment Variables"

    ```python
    --8<-- "examples/docs/features/configure/advanced_configure_env.py"
    ```

=== "common_app.yaml"

    ```yaml
    --8<-- "examples/docs/shared/common_app.yaml"
    ```

### MaskingConfig

```python
--8<-- "src/dature/config.py:masking-config"
```

### ErrorDisplayConfig

```python
--8<-- "src/dature/config.py:error-display-config"
```

### LoadingConfig

```python
--8<-- "src/dature/config.py:loading-config"
```

### type_loaders

Register global custom type loaders that apply to all `dature.load()` calls. See [Custom Types & Loaders](../advanced/custom_types.md#per-source-vs-global).

## Environment Variables

dature auto-loads its own config from `DATURE_*` environment variables on first use. Nested fields use `__` as delimiter:

| Variable | Config | Field | Description |
|---|---|---|---|
| `DATURE_MASKING__MASK` | [MaskingConfig](#maskingconfig) | `mask` | Replacement string for masked values |
| `DATURE_MASKING__VISIBLE_PREFIX` | [MaskingConfig](#maskingconfig) | `visible_prefix` | Number of characters left visible at the start |
| `DATURE_MASKING__VISIBLE_SUFFIX` | [MaskingConfig](#maskingconfig) | `visible_suffix` | Number of characters left visible at the end |
| `DATURE_MASKING__MIN_HEURISTIC_LENGTH` | [MaskingConfig](#maskingconfig) | `min_heuristic_length` | Minimum field value length for auto-detection of secrets by field name |
| `DATURE_MASKING__HEURISTIC_THRESHOLD` | [MaskingConfig](#maskingconfig) | `heuristic_threshold` | Uncommon bigram ratio threshold for heuristic secret detection (0.0–1.0) |
| `DATURE_MASKING__MASK_SECRETS` | [MaskingConfig](#maskingconfig) | `mask_secrets` | Enable or disable secret masking globally |
| `DATURE_ERROR_DISPLAY__MAX_VISIBLE_LINES` | [ErrorDisplayConfig](#errordisplayconfig) | `max_visible_lines` | Max lines shown in error messages for source file previews |
| `DATURE_ERROR_DISPLAY__MAX_LINE_LENGTH` | [ErrorDisplayConfig](#errordisplayconfig) | `max_line_length` | Max character width per line in error messages |
| `DATURE_LOADING__CACHE` | [LoadingConfig](#loadingconfig) | `cache` | Enable caching for decorator-mode loads |
| `DATURE_LOADING__DEBUG` | [LoadingConfig](#loadingconfig) | `debug` | Attach `LoadReport` to every loaded instance |
| `DATURE_LOADING__NESTED_RESOLVE_STRATEGY` | [LoadingConfig](#loadingconfig) | `nested_resolve_strategy` | Default priority for JSON vs flat keys: `flat` (default) or `json`. See [Nested Resolve](../advanced/nested-resolve.md) |
| `DATURE_LOADING__EXPAND_ENV_VARS` | [LoadingConfig](#loadingconfig) | `expand_env_vars` | Default env var expansion mode: `default`, `disabled`, `empty`, or `strict`. See [Env Expansion](../advanced/env-expansion.md) |
| `DATURE_LOADING__SEARCH_SYSTEM_PATHS` | [LoadingConfig](#loadingconfig) | `search_system_paths` | Enable automatic config file search in standard system locations (`~/.config/`, `/etc/`, `%APPDATA%/`). See [Config Search](../advanced/config-search.md) |
| `DATURE_LOADING__SYSTEM_CONFIG_DIRS` | [LoadingConfig](#loadingconfig) | `system_config_dirs` | Custom colon-separated list of directories for config file search (overrides auto-detection) |
