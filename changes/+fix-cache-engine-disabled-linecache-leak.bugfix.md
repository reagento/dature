With `cache_engine=False` (the default), every `load()` call compiled a fresh `adaptix` `Retort`
from scratch and discarded it, but `adaptix`'s codegen unconditionally left the compiled source
of each loader behind in Python's process-global `linecache.cache` for traceback readability,
never evicting it. A `Loader` (or `@load(...)`-decorated class) called repeatedly with
`cache=False` would grow that cache without bound for the life of the process. `RetortCache` now
purges the `linecache` entries it registered once each `load()` call finishes using them, whenever
`cache_engine` is disabled.
