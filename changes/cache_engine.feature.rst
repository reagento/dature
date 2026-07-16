Added ``cache_engine: bool | None`` — a new load-time option (``dature.load(...)``, ``Loader``,
and ``configure(loading={...})``) that controls whether the compiled engine dature builds
internally to convert raw source data into your dataclass is retained across loads, independent
of ``cache`` (which caches the *loaded result*).

- ``cache_engine=False`` (the default) — nothing about the compiled engine survives a load; it is
  built fresh every time and discarded. A decorated class now retains only a fraction of the
  memory it used to (~30 KiB vs ~100 KiB for a flat 8-field schema).
- ``cache_engine=True`` — the compiled engine is kept alive for the ``Loader``/class lifetime, so
  repeated loads skip recompiling it. This is the opt-in for a fast, uncached hot path
  (``cache=False`` with frequent reloads).

The default pairs ``cache=True`` (caches forever) with ``cache_engine=False``, since a cached
result never needs to recompile the engine again anyway. See the
`caching docs <https://dature.readthedocs.io/en/latest/advanced/caching/#cache_engine-retaining-the-compiled-engine>`_
and the updated `benchmarks <https://dature.readthedocs.io/en/latest/comparison/benchmarks/>`_ for
the concrete speed/memory trade-off.
