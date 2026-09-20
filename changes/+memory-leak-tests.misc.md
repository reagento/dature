Added `tests/memory/`, a regression suite around every public form of `load()` (function mode,
`@load(...)`, `Loader.load`, `Dature().load`, `Dature().loader`) that fails if repeated loads
retain live objects or process memory. Marked `memory` and excluded from the main test matrix —
it runs in its own CI job instead.
