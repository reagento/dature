"""Memory benchmark — peak KiB allocated per full cycle, dature vs competitors.

Each source/experiment table shows one full-cycle build+load per variant (model declaration
+ source + loader + load), measured in-process. The library import is a one-time resident
cost measured separately in bench_import.py, not here (a warmup call pulls the library into
sys.modules, so the measured runs capture only build + load). A WARM reuse section
(dature-only) shows the steady state with a pre-built / cached loader.

tracemalloc tracks the Python heap only; pydantic-settings' Rust extension (pydantic_core)
allocates outside it, so its numbers are understated.

Run: uv run --group benchmarks python benchmarks/bench_memory.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import examples_warm
import prepare  # noqa: F401  (import creates temp files + exports path env vars)
from _common import clear_env_vars, print_mem_table, run_mem_bench, set_env_vars
from bench_speed import EXPERIMENTS, SOURCES

import examples


def main() -> None:
    set_env_vars()
    try:
        print("\n" + "#" * 72)
        print("  Full cycle: build + load (library import excluded — see bench_import.py)")
        print("#" * 72)
        for title, entries in {**SOURCES, **EXPERIMENTS}.items():
            results = [(label, *run_mem_bench(getattr(examples, fn))) for label, fn in entries]
            print_mem_table(title, results)

        print("\n" + "#" * 72)
        print("  WARM reuse — dature only, hot path over a pre-built loader")
        print("#" * 72)
        warm = [
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
