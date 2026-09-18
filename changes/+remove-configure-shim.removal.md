Removed `dature.configure()`, deprecated since 1.3 with removal announced for 1.5. Migrate to
`dature.Dature(...)`, which accepts the same option groups (`vault=`, `masking=`, `loading=`, ...).
The process-wide override is gone along with it — `DATURE_*` environment variables are now the
only way to set configuration for the whole process.
