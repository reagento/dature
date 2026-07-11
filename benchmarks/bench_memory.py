"""Memory benchmark — dature vs competitors, two metrics chosen to fit what each measures.

Build + load: retained RSS per fresh build (KiB), measured as process RSS growth over N builds
whose results are kept alive. RSS (not tracemalloc) because tracemalloc sees only the Python
heap — pydantic-settings does most of its schema work in a Rust extension (pydantic_core) that
tracemalloc cannot see, which would understate it by ~20x and make the comparison meaningless.
RSS counts native allocations too, so it's a fair cross-library number.

Warm reuse: tracemalloc peak per hot call. Here nothing stays resident (the loader is pre-built
and reused), so RSS-delta would read ~0; tracemalloc correctly captures the per-call allocation
churn. This section is dature-only (the steady state with a pre-built / cached loader).

The library import is a one-time cost measured separately in bench_import.py, not here.

Run: uv run --group benchmarks python benchmarks/bench_memory.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import prepare  # noqa: F401  (import creates temp files + exports path env vars)
from _common import clear_env_vars, print_mem_table, run_mem_bench, run_rss_bench, set_env_vars
from bench_scenarios import EXPERIMENTS, SOURCES

# NOTE: examples_warm is imported lazily inside main() *after* the RSS section. Importing it at
# module level eagerly builds adaptix loaders (and loads pydantic_core); on macOS a subprocess
# spawned from such a parent can crash, and run_rss_bench spawns one child per row. Keeping the
# parent light until the RSS section is done avoids that.


def main() -> None:
    set_env_vars()
    try:
        # build + load: retained RSS per fresh build. RSS (not tracemalloc) so the comparison is
        # fair to native-extension libs — pydantic_core's Rust allocations are invisible to
        # tracemalloc but counted here. Each object is kept alive; RSS growth / N is the footprint.
        print("\n" + "#" * 72)
        print("  Full cycle: build + load — retained RSS/build (import excluded; sees Rust/native)")
        print("#" * 72)
        for title, entries in {**SOURCES, **EXPERIMENTS}.items():
            # hydra is excluded: it can't be built in a tight loop (GlobalHydra is a process
            # singleton) and returns an untyped DictConfig, not a comparable typed dataclass.
            rss_entries = [(label, fn) for label, fn in entries if fn != "hydra_yaml"]
            results = [(label, *run_rss_bench(fn)) for label, fn in rss_entries]
            print_mem_table(title, results)

        # Warm reuse: tracemalloc is the right tool here — it measures the transient Python
        # allocation churn per hot call (nothing stays resident, so RSS-delta would read ~0).
        import examples_warm  # noqa: PLC0415 — deferred until after RSS spawns (see NOTE above)

        print("\n" + "#" * 72)
        print("  WARM reuse — dature only, tracemalloc peak per hot call")
        print("#" * 72)
        warm = [
            ("dature (func, fixed schema, no reuse)", *run_mem_bench(examples_warm.dature_env_func_fixed_schema)),
            ("dature (decorator, hot)", *run_mem_bench(examples_warm.dature_env_hot)),
            ("dature (Loader reuse)", *run_mem_bench(examples_warm.dature_env_loader)),
            ("dature (cache=True)", *run_mem_bench(examples_warm.dature_env_cached)),
            ("dature (cache=timedelta)", *run_mem_bench(examples_warm.dature_env_cached_ttl)),
            ("pydantic-settings (reuse)", *run_mem_bench(examples_warm.pydantic_env_reuse)),
        ]
        print_mem_table("Warm reuse  (8 ENV fields, hot path only)", warm)
    finally:
        clear_env_vars()


if __name__ == "__main__":
    main()
