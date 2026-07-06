"""Multi-source merge benchmark: JSON file defaults + ENV var overrides.

Scenario: JSON file provides base config; environment variables with BENCH_ prefix
override selected fields. Each library must read both sources and merge them.

hydra: YAML-only, no native ENV merge without custom resolvers — excluded.
python-decouple: not designed for multi-source merging — excluded.

Run: uv run --group benchmarks python benchmarks/bench_multi_source.py
"""

import atexit
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BenchConfig, clear_env_vars, print_table, run_bench, set_env_vars, write_json
from dynaconf import Dynaconf
from pydantic_settings import BaseSettings, JsonConfigSettingsSource, SettingsConfigDict

import dature

# --- temp file setup ---
_tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
json_path = Path(_tmp.name)
_tmp.close()
write_json(json_path)
atexit.register(json_path.unlink, missing_ok=True)

# dature: two sources declared upfront
_json_source = dature.JsonSource(file=json_path)  # Source 1: JSON file (base)
_env_source = dature.EnvSource(prefix="BENCH_")  # Source 2: BENCH_* env vars (override)


# pydantic-settings: JSON + env sources combined via settings_customise_sources
class _PydanticMultiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BENCH_", env_file=None)

    host: str
    port: int
    debug: bool
    max_connections: int
    timeout: float
    db_name: str
    workers: int
    log_level: str

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        # env_settings (BENCH_* env vars) takes priority over JsonConfigSettingsSource
        return (env_settings, JsonConfigSettingsSource(settings_cls, json_file=str(json_path)))


_DatureDecorated = dature.load(_json_source, _env_source, cache=False, strategy="last_wins")(BenchConfig)

# dynaconf: two sources pre-configured at module level; reload() re-reads both each call
_dynaconf_multi = Dynaconf(
    settings_files=[str(json_path)],  # Source 1: JSON file (base values)
    envvar_prefix="BENCH",  # Source 2: BENCH_* env vars (override)
    environments=False,
    load_dotenv=False,
)


def dature_load() -> BenchConfig:
    return dature.load(_json_source, _env_source, schema=BenchConfig, strategy="last_wins")


def dature_decorator_hot() -> BenchConfig:
    return _DatureDecorated()


def dature_decorator_startup():
    dature.load(_json_source, _env_source, cache=False, strategy="last_wins")(BenchConfig)


def pydantic_load() -> _PydanticMultiSettings:
    return _PydanticMultiSettings()


def dynaconf_load() -> BenchConfig:
    _dynaconf_multi.reload()  # re-read from both sources on each call
    return BenchConfig(
        host=_dynaconf_multi.HOST,
        port=int(_dynaconf_multi.PORT),
        debug=bool(_dynaconf_multi.DEBUG),
        max_connections=int(_dynaconf_multi.MAX_CONNECTIONS),
        timeout=float(_dynaconf_multi.TIMEOUT),
        db_name=_dynaconf_multi.DB_NAME,
        workers=int(_dynaconf_multi.WORKERS),
        log_level=_dynaconf_multi.LOG_LEVEL,
    )


if __name__ == "__main__":
    set_env_vars()
    try:
        results = [
            ("dature (func mode)", *run_bench(dature_load)),
            ("dature (decorator, hot)", *run_bench(dature_decorator_hot)),
            ("pydantic-settings", *run_bench(pydantic_load)),
            ("dynaconf", *run_bench(dynaconf_load)),
        ]
        print_table(
            "Multi-source merge  (JSON defaults + ENV overrides → typed dataclass)",
            results,
        )
        print("  Note: python-decouple excluded (no multi-source merge)")
        print("  Note: hydra excluded (YAML only, no native ENV merge)")

        startup = [("dature (decorator, startup)", *run_bench(dature_decorator_startup))]
        print_table("dature decorator — one-time startup cost", startup)
    finally:
        clear_env_vars()
