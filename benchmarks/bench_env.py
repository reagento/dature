"""ENV loading benchmark: dature vs pydantic-settings vs python-decouple vs dynaconf.

Each library reads 8 fields from os.environ into a typed dataclass.
Env vars use BENCH_ prefix to avoid clashing with real environment variables.

Run: uv run --group benchmarks python benchmarks/bench_env.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BenchConfig, clear_env_vars, print_table, run_bench, set_env_vars
from decouple import config as decouple_config
from dynaconf import Dynaconf
from pydantic_settings import BaseSettings, SettingsConfigDict

import dature

_env_source = dature.EnvSource(prefix="BENCH_")
_DatureDecorated = dature.load(_env_source, cache=False)(BenchConfig)


class _PydanticEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BENCH_", env_file=None)

    host: str
    port: int
    debug: bool
    max_connections: int
    timeout: float
    db_name: str
    workers: int
    log_level: str


def dature_load() -> BenchConfig:
    return dature.load(_env_source, schema=BenchConfig)


def dature_decorator_hot() -> BenchConfig:
    return _DatureDecorated()


def dature_decorator_startup():
    dature.load(_env_source, cache=False)(BenchConfig)


def pydantic_load() -> _PydanticEnvSettings:
    return _PydanticEnvSettings()


def decouple_load() -> BenchConfig:
    return BenchConfig(
        host=decouple_config("BENCH_HOST"),
        port=decouple_config("BENCH_PORT", cast=int),
        debug=decouple_config("BENCH_DEBUG", cast=bool),
        max_connections=decouple_config("BENCH_MAX_CONNECTIONS", cast=int),
        timeout=decouple_config("BENCH_TIMEOUT", cast=float),
        db_name=decouple_config("BENCH_DB_NAME"),
        workers=decouple_config("BENCH_WORKERS", cast=int),
        log_level=decouple_config("BENCH_LOG_LEVEL"),
    )


def dynaconf_load() -> BenchConfig:
    settings = Dynaconf(envvar_prefix="BENCH", environments=False)
    return BenchConfig(
        host=settings.HOST,
        port=int(settings.PORT),
        debug=bool(settings.DEBUG),
        max_connections=int(settings.MAX_CONNECTIONS),
        timeout=float(settings.TIMEOUT),
        db_name=settings.DB_NAME,
        workers=int(settings.WORKERS),
        log_level=settings.LOG_LEVEL,
    )


if __name__ == "__main__":
    set_env_vars()
    try:
        results = [
            ("dature (func mode)", *run_bench(dature_load)),
            ("dature (decorator, hot)", *run_bench(dature_decorator_hot)),
            ("pydantic-settings", *run_bench(pydantic_load)),
            ("python-decouple", *run_bench(decouple_load)),
            ("dynaconf", *run_bench(dynaconf_load)),
        ]
        print_table("ENV loading  (8 fields, os.environ → typed dataclass)", results)

        startup = [("dature (decorator, startup)", *run_bench(dature_decorator_startup))]
        print_table("dature decorator — one-time startup cost", startup)
    finally:
        clear_env_vars()
