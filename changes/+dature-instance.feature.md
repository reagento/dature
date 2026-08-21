Added `dature.Dature` — an explicit, immutable configuration instance that replaces the global `configure()` call.

`Dature(masking={...}, error_display={...}, vault={...}, ...)` accepts all `DatureConfig` groups and merges them on top of the process-wide `DATURE_*`-derived defaults.
Each instance is fully independent: multiple instances with different settings coexist without affecting each other or the process-wide defaults.

```python
conf = dature.Dature(vault={"host": "vault.internal"})

# Function mode
result = conf.load(dature.VaultSource(path="secrets"), schema=Settings)

# Decorator mode (config binds at decoration/import time)
@conf.load(dature.VaultSource(path="secrets"))
@dataclass
class Settings:
    host: str
    port: int

# Build a reusable Loader with caching
loader = conf.loader(dature.VaultSource(path="secrets"), schema=Settings)
```

`dature.load(...)` is unchanged and continues to work as the default entry point.

`Dature.replace(**groups)` creates a new instance with individual groups overridden, inheriting all other groups from the current instance.

`error_display` (`max_visible_lines`, `max_line_length`) is overridable per instance the same way every other config group is, closing the last env-only group:

```python
narrow = dature.Dature(error_display={"max_line_length": 40})
wide = dature.Dature(error_display={"max_line_length": 200})
```

Two instances loading the same broken config now render the same failure differently, and the override survives across `except*`-caught exception groups (the underlying `FieldLoadError`/`MergeConflictFieldError`/`MissingEnvVarError` leaves each carry their own `ErrorDisplayConfig`). `error_display` is now visible in `repr(Dature(...))` alongside the other groups. Omitting `error_display` inherits the process-wide `DATURE_ERROR_DISPLAY__*`-derived default, unchanged from before.

`dature.configure()` is now deprecated and will be removed in **dature 1.5**. Migrate to `dature.Dature(...)`, which accepts the same option groups and merges them on top of the `DATURE_*` environment defaults:

```python
# Before
dature.configure(vault={"host": "vault.internal"})
result = dature.load(VaultSource(path="secrets"), schema=Settings)

# After
conf = dature.Dature(vault={"host": "vault.internal"})
result = conf.load(VaultSource(path="secrets"), schema=Settings)
```

Calling `configure()` emits a `DeprecationWarning` with migration instructions. The `dature.load()` free function is unchanged.
