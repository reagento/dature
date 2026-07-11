Made the memory benchmark honest across libraries. Build+load memory is now reported as
retained RSS per build (measured in a fresh subprocess), which counts native-extension
allocations — pydantic-settings does most of its work in a Rust core that ``tracemalloc``
cannot see, so the old ``tracemalloc``-peak column overstated dature's cost ~20× (its transient
codegen scratch vs pydantic's invisible Rust). By RSS the two are comparable (~31 KiB vs ~28 KiB
per build). ``tracemalloc`` is kept only for the warm-reuse table, where it is the correct tool.
Scenario tables moved to ``benchmarks/bench_scenarios.py``.
