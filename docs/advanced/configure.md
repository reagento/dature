# Configure

## Caching

In decorator mode, caching is enabled by default:

```python
--8<-- "examples/docs/advanced_caching.py"
```

Caching can also be configured globally via `configure()`.

## Global configure()

Customize defaults for the entire application — programmatically or via environment variables:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_configure.py"
    ```

=== "app.yaml"

    ```yaml
    --8<-- "examples/docs/sources/app.yaml"
    ```

=== "Environment Variables"

    dature auto-loads its own config from `DATURE_*` environment variables on first use. Nested fields use `__` as delimiter:

    ```bash
    export DATURE_MASKING__MASK_CHAR="X"
    export DATURE_MASKING__MIN_VISIBLE_CHARS="1"
    export DATURE_ERROR_DISPLAY__MAX_VISIBLE_LINES="5"
    export DATURE_LOADING__DEBUG="false"
    export DATURE_LOADING__CACHE="true"
    ```

    ```python
    --8<-- "examples/docs/advanced_configure_env.py"
    ```

### MaskingConfig

```python
@dataclass(frozen=True, slots=True)
class MaskingConfig:
    mask_char: str = "*"
    min_visible_chars: int = 2
    min_length_for_partial_mask: int = 5
    fixed_mask_length: int = 5
    min_heuristic_length: int = 8
    secret_field_names: tuple[str, ...] = (
        "password", "passwd", "secret", "token",
        "api_key", "apikey", "api_secret", "access_key",
        "private_key", "auth", "credential",
    )
    mask_secrets: bool = True
```

### ErrorDisplayConfig

```python
@dataclass(frozen=True, slots=True)
class ErrorDisplayConfig:
    max_visible_lines: int = 3
    max_line_length: int = 80
```

### LoadingConfig

```python
@dataclass(frozen=True, slots=True)
class LoadingConfig:
    cache: bool = True
    debug: bool = False
```
