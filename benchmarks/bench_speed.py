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

import examples

# (label, examples function name) per table — order = display order
SOURCES: dict[str, list[tuple[str, str]]] = {
    "ENV  (os.environ → typed dataclass)": [
        ("dature (func)", "dature_env"),
        ("dature (decorator)", "dature_env_dec"),
        ("pydantic-settings", "pydantic_env"),
        ("python-decouple", "decouple_env"),
        ("dynaconf", "dynaconf_env"),
    ],
    "ENV file (.env → typed dataclass)": [
        ("dature (func)", "dature_dotenv"),
        ("dature (decorator)", "dature_dotenv_dec"),
        ("pydantic-settings", "pydantic_dotenv"),
        ("python-decouple", "decouple_dotenv"),
        ("dynaconf", "dynaconf_dotenv"),
    ],
    "JSON file (→ typed dataclass)": [
        ("dature (func)", "dature_json"),
        ("dature (decorator)", "dature_json_dec"),
        ("pydantic-settings", "pydantic_json"),
        ("dynaconf", "dynaconf_json"),
    ],
    "TOML file (→ typed dataclass)": [
        ("dature (func)", "dature_toml"),
        ("dature (decorator)", "dature_toml_dec"),
        ("pydantic-settings", "pydantic_toml"),
        ("dynaconf", "dynaconf_toml"),
    ],
    "YAML file (→ typed dataclass / DictConfig)": [
        ("dature (func)", "dature_yaml"),
        ("dature (decorator)", "dature_yaml_dec"),
        ("pydantic-settings", "pydantic_yaml"),
        ("dynaconf", "dynaconf_yaml"),
        ("hydra (DictConfig, not typed)", "hydra_yaml"),
    ],
}

EXPERIMENTS: dict[str, list[tuple[str, str]]] = {
    "Nested model, 5 levels deep (ENV source)": [
        ("dature (func)", "dature_nested"),
        ("dature (decorator)", "dature_nested_dec"),
        ("pydantic-settings", "pydantic_nested"),
    ],
    "Three models loaded at once (ENV source)": [
        ("dature (func)", "dature_multi_model"),
        ("dature (decorator)", "dature_multi_model_dec"),
        ("pydantic-settings", "pydantic_multi_model"),
        ("dynaconf", "dynaconf_multi_model"),
    ],
}


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
            ("dature (decorator, hot)", *run_bench(examples_warm.dature_env_hot)),
            ("dature (Loader reuse)", *run_bench(examples_warm.dature_env_loader)),
            ("dature (cache=True)", *run_bench(examples_warm.dature_env_cached)),
            ("dature (cache=timedelta)", *run_bench(examples_warm.dature_env_cached_ttl)),
            ("pydantic-settings (reuse)", *run_bench(examples_warm.pydantic_env_reuse)),
        ]
        print_table("Warm reuse  (8 ENV fields, hot path only)", warm)
    finally:
        clear_env_vars()


if __name__ == "__main__":
    main()
