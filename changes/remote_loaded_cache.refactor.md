Removed mutable `_loaded_cache` state from `RemoteSource`. Raw fetch results are now
forwarded explicitly via `LoadRawResult.loaded_data` and carried in the per-source
rendering context (alongside `file_content`) rather than stored on the source DTO itself.
This makes `Source` a pure config DTO with no runtime state.

Deleted the unused `create_retort`, `create_probe_retort`, and `create_validating_retort`
factory functions — all retort construction now goes through `RetortCache` which builds
variants via `Retort.extend()`.
