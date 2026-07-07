"""Speed benchmark: µs per call — dature vs pydantic-settings vs python-decouple vs dynaconf vs hydra.

Covers all source types: ENV, JSON, TOML, YAML, .env, multi-source, caching.
Shared fixtures live in prepare.py.

Run: uv run --group benchmarks python benchmarks/bench_speed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import clear_env_vars, print_table, run_bench, set_env_vars
from hydra.core.global_hydra import GlobalHydra
from prepare import (
    dature_cache_eternal,
    dature_cache_none,
    dature_cache_ttl,
    dature_dotenv_func,
    dature_dotenv_hot,
    dature_dotenv_loader,
    dature_dotenv_startup,
    dature_env_func,
    dature_env_hot,
    dature_env_loader,
    dature_env_startup,
    dature_json_func,
    dature_json_hot,
    dature_json_loader,
    dature_json_startup,
    dature_multi_func,
    dature_multi_hot,
    dature_multi_loader,
    dature_multi_startup,
    dature_toml_func,
    dature_toml_hot,
    dature_toml_loader,
    dature_toml_startup,
    dature_yaml_func,
    dature_yaml_hot,
    dature_yaml_loader,
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
            ("dature (func mode)", *run_bench(dature_env_func)),
            ("dature (Loader reuse)", *run_bench(dature_env_loader)),
            ("dature (decorator, hot)", *run_bench(dature_env_hot)),
            ("pydantic-settings", *run_bench(pydantic_env)),
            ("python-decouple", *run_bench(decouple_env)),
            ("dynaconf", *run_bench(dynaconf_env)),
        ]
        print_table("ENV loading  (8 fields, os.environ → typed dataclass)", results)
        startup = [("dature (decorator, startup)", *run_bench(dature_env_startup))]
        print_table("dature decorator — one-time startup cost", startup)

        # JSON file loading
        results = [
            ("dature (func mode)", *run_bench(dature_json_func)),
            ("dature (Loader reuse)", *run_bench(dature_json_loader)),
            ("dature (decorator, hot)", *run_bench(dature_json_hot)),
            ("pydantic-settings", *run_bench(pydantic_json)),
            ("dynaconf", *run_bench(dynaconf_json)),
        ]
        print_table("JSON file loading  (8 fields, file → typed dataclass)", results)
        print("  Note: python-decouple excluded (no JSON file support). hydra: YAML only.")
        startup = [("dature (decorator, startup)", *run_bench(dature_json_startup))]
        print_table("dature decorator — one-time startup cost", startup)

        # TOML file loading
        results = [
            ("dature (func mode)", *run_bench(dature_toml_func)),
            ("dature (Loader reuse)", *run_bench(dature_toml_loader)),
            ("dature (decorator, hot)", *run_bench(dature_toml_hot)),
            ("pydantic-settings", *run_bench(pydantic_toml)),
            ("dynaconf", *run_bench(dynaconf_toml)),
        ]
        print_table("TOML file loading  (8 fields, file → typed dataclass)", results)
        print("  Note: python-decouple excluded (no TOML file support). hydra: YAML only.")
        startup = [("dature (decorator, startup)", *run_bench(dature_toml_startup))]
        print_table("dature decorator — one-time startup cost", startup)

        # YAML file loading
        GlobalHydra.instance().clear()
        results = [
            ("dature (func mode)", *run_bench(dature_yaml_func)),
            ("dature (Loader reuse)", *run_bench(dature_yaml_loader)),
            ("dature (decorator, hot)", *run_bench(dature_yaml_hot)),
            ("pydantic-settings", *run_bench(pydantic_yaml)),
            ("dynaconf", *run_bench(dynaconf_yaml)),
            ("hydra (DictConfig, not typed)", *run_bench(hydra_yaml)),
        ]
        print_table("YAML file loading  (8 fields, file → typed dataclass / DictConfig)", results)
        print("  Note: python-decouple excluded (no YAML file support)")
        print("  Note: hydra result is OmegaConf DictConfig, includes singleton reset overhead")
        startup = [("dature (decorator, startup)", *run_bench(dature_yaml_startup))]
        print_table("dature decorator — one-time startup cost", startup)

        # .env file loading
        results = [
            ("dature (func mode)", *run_bench(dature_dotenv_func)),
            ("dature (Loader reuse)", *run_bench(dature_dotenv_loader)),
            ("dature (decorator, hot)", *run_bench(dature_dotenv_hot)),
            ("pydantic-settings", *run_bench(pydantic_dotenv)),
            ("python-decouple", *run_bench(decouple_dotenv)),
            ("dynaconf", *run_bench(dynaconf_dotenv)),
        ]
        print_table("ENV file (.env) loading  (8 fields, file → typed dataclass)", results)
        print("  Note: hydra excluded (no .env file support)")
        startup = [("dature (decorator, startup)", *run_bench(dature_dotenv_startup))]
        print_table("dature decorator — one-time startup cost", startup)

        # Multi-source
        results = [
            ("dature (func mode)", *run_bench(dature_multi_func)),
            ("dature (Loader reuse)", *run_bench(dature_multi_loader)),
            ("dature (decorator, hot)", *run_bench(dature_multi_hot)),
            ("pydantic-settings", *run_bench(pydantic_multi)),
            ("dynaconf", *run_bench(dynaconf_multi)),
        ]
        print_table("Multi-source merge  (JSON defaults + ENV overrides → typed dataclass)", results)
        print("  Note: python-decouple excluded (no multi-source merge). hydra: YAML only.")
        startup = [("dature (decorator, startup)", *run_bench(dature_multi_startup))]
        print_table("dature decorator — one-time startup cost", startup)

        # Caching — fresh
        fresh_results = [
            ("dature (func mode)", *run_bench(dature_env_func)),
            ("dature (decorator, no cache)", *run_bench(dature_cache_none)),
            ("pydantic-settings", *run_bench(pydantic_env)),
            ("python-decouple", *run_bench(decouple_env)),
            ("dynaconf", *run_bench(dynaconf_env)),
        ]
        print_table("Fresh load every call  (no caching, 8 ENV fields)", fresh_results)
        startup = [("dature (decorator, startup)", *run_bench(dature_env_startup))]
        print_table("dature decorator — one-time startup cost", startup)

        # Caching — cached
        cached_results = [
            ("dature decorator (cache=True)", *run_bench(dature_cache_eternal)),
            ("dature decorator (cache=timedelta)", *run_bench(dature_cache_ttl)),
            ("pydantic-settings + @lru_cache", *run_bench(pydantic_cached)),
            ("python-decouple + @lru_cache", *run_bench(decouple_cached)),
            ("dynaconf + @lru_cache", *run_bench(dynaconf_cached)),
        ]
        print_table("Cached load  (8 ENV fields)", cached_results)
        print("  Note: @lru_cache has no TTL — cache never expires. dature's cache=timedelta supports TTL natively.")

    finally:
        clear_env_vars()
