Refreshed the numbers in `docs/comparison/benchmarks.md` against a hardened benchmark harness:
`benchmarks/_common.py`'s `run_bench` now warms up each callable before timing (a dature build's
first call pays ~35x a steady-state call for adaptix's lazy init and the one-time config
bootstrap) and reports `min` instead of `mean` across repeats; `benchmarks/bench_import.py`
discards one untimed sample per fresh venv before measuring. Previous runs could read up to 2x
higher purely from that noise, not from an actual dature slowdown.
