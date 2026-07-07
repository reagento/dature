Added ``docs/comparison/benchmarks.md`` with performance benchmarks comparing dature
against pydantic-settings, python-decouple, dynaconf, and hydra across seven scenarios:
ENV loading, JSON/TOML/YAML/.env file loading, multi-source merge, and caching.
Added standalone ``benchmarks/`` scripts (``timeit``-based, no pytest) and a
``benchmarks`` dependency group in ``pyproject.toml``.
