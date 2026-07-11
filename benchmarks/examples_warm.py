"""Warm reuse scenarios: the hot path once the object is built once and reused.

All library imports and object construction happen at module level; each benchmark measures
only the reuse. dature: hot decorator, Loader reuse, caching. pydantic-settings: a pre-built
Settings class, re-instantiated (its schema is cached on the class). Driven in-process through
``run_bench`` / ``run_mem_bench``.
"""

import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from pydantic_settings import BaseSettings, SettingsConfigDict

import dature
from dature import EnvSource, Loader


@dataclass
class BenchConfig:
    host: str
    port: int
    debug: bool
    max_connections: int
    timeout: float
    db_name: str
    workers: int
    log_level: str


_env_source = EnvSource(prefix="BENCH_")

# hot decorator (cache=False): Loader built once at decoration time, reused per call
_HotEnvCfg = dature.load(_env_source, cache=False)(BenchConfig)
# Loader reuse: explicit Loader kept at module level, .load() called repeatedly
_loader_env = Loader(_env_source, schema=BenchConfig, cache=False)
# caching variants (eternal and TTL) — cache hit after the first warmup call
_CachedEnvCfg = dature.load(_env_source, cache=True)(BenchConfig)
_CachedTTLCfg = dature.load(_env_source, cache=timedelta(minutes=5))(BenchConfig)


class _PydanticEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BENCH_")
    host: str
    port: int
    debug: bool
    max_connections: int
    timeout: float
    db_name: str
    workers: int
    log_level: str


def dature_env_func_fixed_schema() -> BenchConfig:
    return dature.load(_env_source, schema=BenchConfig)


def dature_env_hot() -> BenchConfig:
    return _HotEnvCfg()


def dature_env_loader() -> BenchConfig:
    return _loader_env.load()


def dature_env_cached() -> BenchConfig:
    return _CachedEnvCfg()


def dature_env_cached_ttl() -> BenchConfig:
    return _CachedTTLCfg()


def pydantic_env_reuse() -> _PydanticEnv:
    return _PydanticEnv()
