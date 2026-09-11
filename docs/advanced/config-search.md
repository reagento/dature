# Automatic Config File Search

By default, all file-based sources automatically search for config files in standard system locations. This feature is enabled by default and works across all platforms.

## Search Order

When you specify a config file, dature searches in the following order:

1. **Specified path** - The path you provide (relative to current working directory or absolute)
2. **User config directories** (platform-specific):
    - **Linux**: `~/.config/`
    - **macOS**: `~/Library/Application Support/`, `~/.config/`
    - **Windows**: `%APPDATA%/`
3. **System config directories** (Linux/macOS only):
    - `/etc/`
    - `/etc/xdg/`

## Examples

=== "Default (Enabled)"

    By default, file-based sources search standard config locations. This example writes `app.yaml` into a directory, where the search occurs, and points the platform config env var there so the loader finds it through system search.

    ```python
    --8<-- "docs/examples/advanced/config_search/default.py:example"
    ```

=== "Custom Directories"

    ```python
    --8<-- "docs/examples/advanced/config_search/custom_dirs.py:example"
    ```

=== "`load()` Keyword"

    `config_dirs` is also a keyword argument on `dature.load()` itself, so it applies to
    every source in the call that doesn't set its own `config_dirs`.

    ```python
    --8<-- "docs/examples/advanced/config_search/load_kwarg.py:example"
    ```

=== "EnvFileSource"

    `config_dirs` works the same way on every file-based source — here it's applied to `EnvFileSource`.

    ```python
    --8<-- "docs/examples/advanced/config_search/env_file_dirs.py:example"
    ```

=== "Disable Globally"

    ```python
    --8<-- "docs/examples/advanced/config_search/disable_global.py:example"
    ```

=== "Disable Per-Source"
    Disable search only for one source while the global setting remains unchanged.
    Even though the global `config_dirs` contains the directory with the file,
    it won't be searched — the source's own `config_dirs=()` overrides it locally.
    ```python
    --8<-- "docs/examples/advanced/config_search/disable_local.py:example"
    ```

=== "common_app.yaml"

    ```yaml
    --8<-- "docs/examples/advanced/shared/common_app.yaml"
    ```

## Configuration

For global and per-source configuration options, see [Configure](../basic/configure.md).

## Environment Variables

The following environment variables affect search paths:

- `XDG_CONFIG_HOME` - Overrides `~/.config/` on Linux/macOS
- `XDG_CONFIG_DIRS` - Overrides `/etc/xdg/` on Linux
- `APPDATA` - Used for Windows user config directory


