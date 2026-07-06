"""Memory benchmark: peak allocation per call (KiB) — dature vs pydantic-settings vs python-decouple vs dynaconf.

Covers all source types: ENV, JSON, TOML, YAML, .env, multi-source, caching.
Shared fixtures live in prepare.py.

tracemalloc tracks Python heap only. pydantic-settings uses a Rust extension (pydantic_core);
its internal allocations are not visible here, so its numbers will be understated.

Run: uv run --group benchmarks python benchmarks/bench_memory.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import clear_env_vars, print_mem_table, run_mem_bench, set_env_vars
from hydra.core.global_hydra import GlobalHydra
from prepare import (
    dature_cache_eternal,
    dature_cache_none,
    dature_cache_ttl,
    dature_dotenv_func,
    dature_dotenv_hot,
    dature_dotenv_startup,
    dature_env_func,
    dature_env_hot,
    dature_env_startup,
    dature_json_func,
    dature_json_hot,
    dature_json_startup,
    dature_multi_func,
    dature_multi_hot,
    dature_multi_startup,
    dature_toml_func,
    dature_toml_hot,
    dature_toml_startup,
    dature_yaml_func,
    dature_yaml_hot,
    dature_yaml_startup,
    decouple_cached,
    decouple_dotenv,
    decouple_env,
    dynaconf_cached,
    dynaconf_dotenv,
    dynaconf_env,
    dynaconf_json,
    dynaconf_multi,
    dynaconf_toml,
    dynaconf_yaml,
    hydra_yaml,
    pydantic_cached,
    pydantic_dotenv,
    pydantic_env,
    pydantic_json,
    pydantic_multi,
    pydantic_toml,
    pydantic_yaml,
)

if __name__ == "__main__":
    set_env_vars()
    try:
        # ENV loading
        results = [
            ("dature (func mode)", *run_mem_bench(dature_env_func)),
            ("dature (decorator, hot)", *run_mem_bench(dature_env_hot)),
            ("pydantic-settings", *run_mem_bench(pydantic_env)),
            ("python-decouple", *run_mem_bench(decouple_env)),
            ("dynaconf", *run_mem_bench(dynaconf_env)),
        ]
        print_mem_table("ENV loading  (8 fields, os.environ → typed dataclass)", results)
        startup = [("dature (decorator, startup)", *run_mem_bench(dature_env_startup))]
        print_mem_table("dature decorator — one-time startup cost (ENV)", startup)

        # JSON file loading
        results = [
            ("dature (func mode)", *run_mem_bench(dature_json_func)),
            ("dature (decorator, hot)", *run_mem_bench(dature_json_hot)),
            ("pydantic-settings", *run_mem_bench(pydantic_json)),
            ("dynaconf", *run_mem_bench(dynaconf_json)),
        ]
        print_mem_table("JSON file loading  (8 fields, file → typed dataclass)", results)
        print("  Note: python-decouple excluded (no JSON file support). hydra: YAML only.")
        startup = [("dature (decorator, startup)", *run_mem_bench(dature_json_startup))]
        print_mem_table("dature decorator — one-time startup cost (JSON)", startup)

        # TOML file loading
        results = [
            ("dature (func mode)", *run_mem_bench(dature_toml_func)),
            ("dature (decorator, hot)", *run_mem_bench(dature_toml_hot)),
            ("pydantic-settings", *run_mem_bench(pydantic_toml)),
            ("dynaconf", *run_mem_bench(dynaconf_toml)),
        ]
        print_mem_table("TOML file loading  (8 fields, file → typed dataclass)", results)
        print("  Note: python-decouple excluded (no TOML file support). hydra: YAML only.")
        startup = [("dature (decorator, startup)", *run_mem_bench(dature_toml_startup))]
        print_mem_table("dature decorator — one-time startup cost (TOML)", startup)

        # YAML file loading
        GlobalHydra.instance().clear()
        results = [
            ("dature (func mode)", *run_mem_bench(dature_yaml_func)),
            ("dature (decorator, hot)", *run_mem_bench(dature_yaml_hot)),
            ("pydantic-settings", *run_mem_bench(pydantic_yaml)),
            ("dynaconf", *run_mem_bench(dynaconf_yaml)),
            ("hydra (DictConfig, not typed)", *run_mem_bench(hydra_yaml)),
        ]
        print_mem_table("YAML file loading  (8 fields, file → typed dataclass / DictConfig)", results)
        print("  Note: python-decouple excluded (no YAML file support)")
        print("  Note: hydra result is OmegaConf DictConfig, includes singleton reset overhead")
        startup = [("dature (decorator, startup)", *run_mem_bench(dature_yaml_startup))]
        print_mem_table("dature decorator — one-time startup cost (YAML)", startup)

        # .env file loading
        results = [
            ("dature (func mode)", *run_mem_bench(dature_dotenv_func)),
            ("dature (decorator, hot)", *run_mem_bench(dature_dotenv_hot)),
            ("pydantic-settings", *run_mem_bench(pydantic_dotenv)),
            ("python-decouple", *run_mem_bench(decouple_dotenv)),
            ("dynaconf", *run_mem_bench(dynaconf_dotenv)),
        ]
        print_mem_table("ENV file (.env) loading  (8 fields, file → typed dataclass)", results)
        print("  Note: hydra excluded (no .env file support)")
        startup = [("dature (decorator, startup)", *run_mem_bench(dature_dotenv_startup))]
        print_mem_table("dature decorator — one-time startup cost (.env)", startup)

        # Multi-source
        results = [
            ("dature (func mode)", *run_mem_bench(dature_multi_func)),
            ("dature (decorator, hot)", *run_mem_bench(dature_multi_hot)),
            ("pydantic-settings", *run_mem_bench(pydantic_multi)),
            ("dynaconf", *run_mem_bench(dynaconf_multi)),
        ]
        print_mem_table("Multi-source merge  (JSON defaults + ENV overrides → typed dataclass)", results)
        print("  Note: python-decouple excluded (no multi-source merge). hydra: YAML only.")
        startup = [("dature (decorator, startup)", *run_mem_bench(dature_multi_startup))]
        print_mem_table("dature decorator — one-time startup cost (multi-source)", startup)

        # Caching — no cache
        no_cache = [("dature (decorator, no cache)", *run_mem_bench(dature_cache_none))]
        print_mem_table("Per-call peak allocation — no caching  (8 ENV fields)", no_cache)

        # Caching — cached
        cached_results = [
            ("dature decorator (cache=True)", *run_mem_bench(dature_cache_eternal)),
            ("dature decorator (cache=timedelta)", *run_mem_bench(dature_cache_ttl)),
            ("pydantic-settings + @lru_cache", *run_mem_bench(pydantic_cached)),
            ("python-decouple + @lru_cache", *run_mem_bench(decouple_cached)),
            ("dynaconf + @lru_cache", *run_mem_bench(dynaconf_cached)),
        ]
        print_mem_table("Cached load  (8 ENV fields)", cached_results)
        print("  Note: @lru_cache has no TTL. dature's cache=timedelta supports TTL natively.")

    finally:
        clear_env_vars()
