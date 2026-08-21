Remove the deprecated `mask_secrets` flag (promised for removal in 1.3) from `load()`, `Loader`,
the `@load(...)` decorator, `configure(masking={...})`, and the `--mask-secrets` CLI flag. Use
`masking_mode` (`"all"` / `"secrets_only"` / `"none"`) instead — `mask_secrets=True` maps to
`masking_mode="secrets_only"`, `mask_secrets=False` maps to `masking_mode="none"`.
