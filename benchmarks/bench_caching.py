"""Caching benchmark: repeated config loads across libraries.

Compares dature's built-in decorator cache (dature.load(...)(Class)) with the
@functools.lru_cache pattern that other libraries require.
All benchmarks read the same 8 ENV fields.

Two tables:
  - "fresh"  — a new load is performed on every call (no caching)
  - "cached" — result is cached after the first call

The cached table shows per-call overhead on hot paths.

Run: uv run --group benchmarks python benchmarks/bench_caching.py
"""

import functools
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BenchConfig, clear_env_vars, print_table, run_bench, set_env_vars
from decouple import config as decouple_config
from dynaconf import Dynaconf
from pydantic_settings import BaseSettings, SettingsConfigDict

import dature

_env_source = dature.EnvSource(prefix="BENCH_")


# ── dature decorator classes (dature.load(source)(Class) form) ──────────────

# No-cache decorator: each Config() call does a full load
_DatureDecorated = dature.load(_env_source, cache=False)(BenchConfig)

# Eternal cache: cached forever after first Config() call
_DatureEternal = dature.load(_env_source, cache=True)(BenchConfig)

# TTL cache: cached within the timedelta window
_DatureTTL = dature.load(_env_source, cache=timedelta(minutes=5))(BenchConfig)


# ── pydantic-settings ────────────────────────────────────────────────────────


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


# ── Fresh load functions (no caching) ───────────────────────────────────────


def dature_func_mode() -> BenchConfig:
    return dature.load(_env_source, schema=BenchConfig)


def dature_decorator_hot() -> _DatureDecorated:
    return _DatureDecorated()


def dature_decorator_startup():
    dature.load(_env_source, cache=False)(BenchConfig)


def pydantic_fresh() -> _PydanticEnvSettings:
    return _PydanticEnvSettings()


def decouple_fresh() -> BenchConfig:
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


def dynaconf_fresh() -> BenchConfig:
    settings = Dynaconf(envvar_prefix="BENCH", environments=False, load_dotenv=False)
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


# ── Cached load functions ────────────────────────────────────────────────────


def dature_cached_eternal() -> _DatureEternal:
    return _DatureEternal()


def dature_cached_ttl() -> _DatureTTL:
    return _DatureTTL()


@functools.lru_cache(maxsize=1)
def _pydantic_once() -> _PydanticEnvSettings:
    return _PydanticEnvSettings()


def pydantic_cached() -> _PydanticEnvSettings:
    return _pydantic_once()


@functools.lru_cache(maxsize=1)
def _decouple_once() -> BenchConfig:
    return decouple_fresh()


def decouple_cached() -> BenchConfig:
    return _decouple_once()


@functools.lru_cache(maxsize=1)
def _dynaconf_once() -> BenchConfig:
    return dynaconf_fresh()


def dynaconf_cached() -> BenchConfig:
    return _dynaconf_once()


if __name__ == "__main__":
    set_env_vars()
    try:
        fresh_results = [
            ("dature (func mode)", *run_bench(dature_func_mode)),
            ("dature (decorator, no cache)", *run_bench(dature_decorator_hot)),
            ("pydantic-settings", *run_bench(pydantic_fresh)),
            ("python-decouple", *run_bench(decouple_fresh)),
            ("dynaconf", *run_bench(dynaconf_fresh)),
        ]
        print_table("Fresh load every call  (no caching, 8 ENV fields)", fresh_results)

        startup = [("dature (decorator, startup)", *run_bench(dature_decorator_startup))]
        print_table("dature decorator — one-time startup cost", startup)

        cached_results = [
            ("dature decorator (cache=True)", *run_bench(dature_cached_eternal)),
            ("dature decorator (cache=timedelta)", *run_bench(dature_cached_ttl)),
            ("pydantic-settings + @lru_cache", *run_bench(pydantic_cached)),
            ("python-decouple + @lru_cache", *run_bench(decouple_cached)),
            ("dynaconf + @lru_cache", *run_bench(dynaconf_cached)),
        ]
        print_table("Cached load  (8 ENV fields)", cached_results)
        print("  Note: @lru_cache has no TTL — cache never expires. dature's cache=timedelta supports TTL natively.")
    finally:
        clear_env_vars()
