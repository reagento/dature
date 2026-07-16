"""Speed benchmark — dature vs pydantic-settings vs python-decouple vs dynaconf vs hydra.

Each source/experiment table shows one full-cycle build+load per variant (model declaration
+ source + loader + load), measured in-process. The library import is a one-time cost measured
separately in bench_import.py, not here. A WARM reuse section (dature-only) shows the steady
state where the loader is built once and reused or cached.

Run: uv run --group benchmarks python benchmarks/bench_speed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import examples_warm
import prepare  # noqa: F401  (import creates temp files + exports path env vars)
from _common import clear_env_vars, print_table, run_bench, set_env_vars
from bench_scenarios import EXPERIMENTS, SOURCES

import examples


def main() -> None:
    set_env_vars()
    try:
        print("\n" + "#" * 72)
        print("  Full cycle: build + load (library import excluded — see bench_import.py)")
        print("#" * 72)
        for title, entries in {**SOURCES, **EXPERIMENTS}.items():
            results = [(label, *run_bench(getattr(examples, fn))) for label, fn in entries]
            print_table(title, results)

        print("\n" + "#" * 72)
        print("  WARM reuse — dature only, hot path over a pre-built loader")
        print("#" * 72)
        warm = [
            ("dature (func, fixed schema, no reuse)", *run_bench(examples_warm.dature_env_func_fixed_schema)),
            ("dature (decorator, hot, cache_engine=True)", *run_bench(examples_warm.dature_env_hot)),
            (
                "dature (decorator, hot, cache_engine=False)",
                *run_bench(examples_warm.dature_env_hot_no_engine_cache),
            ),
            ("dature (Loader reuse, cache_engine=True)", *run_bench(examples_warm.dature_env_loader)),
            ("dature (cache=True)", *run_bench(examples_warm.dature_env_cached)),
            ("dature (cache=timedelta)", *run_bench(examples_warm.dature_env_cached_ttl)),
            ("pydantic-settings (reuse)", *run_bench(examples_warm.pydantic_env_reuse)),
        ]
        print_table("Warm reuse  (8 ENV fields, hot path only)", warm)
    finally:
        clear_env_vars()


if __name__ == "__main__":
    main()
