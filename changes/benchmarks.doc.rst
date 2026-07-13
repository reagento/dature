Added ``docs/comparison/benchmarks.md`` with performance benchmarks comparing dature against
pydantic-settings, python-decouple, dynaconf, and hydra across seven scenarios: ENV loading,
JSON/TOML/YAML/.env file loading, multi-source merge, and caching. Added standalone
``benchmarks/`` scripts (``timeit``-based, no pytest) and a ``benchmarks`` dependency group in
``pyproject.toml``.

Build+load memory is reported as retained RSS per build (measured in a fresh subprocess), which
counts native-extension allocations — pydantic-settings does most of its work in a Rust core that
``tracemalloc`` cannot see, so an RSS number is a fair cross-library comparison. ``tracemalloc`` is
used only for the warm-reuse table, where nothing new stays resident and it is the correct tool.
