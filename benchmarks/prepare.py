"""Shared fixture module for bench_speed.py and bench_memory.py.

Sets up temp files, dature sources, pre-warmed decorator objects, pydantic classes,
and all load functions used by both benchmark runners. Not meant to be run directly.
"""

import atexit
import functools
import shutil
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BenchConfig, write_dotenv, write_json, write_toml, write_yaml
from decouple import Config as DecoupleConfig
from decouple import RepositoryEnv
from decouple import config as decouple_config
from dynaconf import Dynaconf
from hydra import compose, initialize_config_dir
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)

import dature
from dature import Loader

# ── Temp file setup ──────────────────────────────────────────────────────────

_json_tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
json_path = Path(_json_tmp.name)
_json_tmp.close()
write_json(json_path)
atexit.register(json_path.unlink, missing_ok=True)

_toml_tmp = tempfile.NamedTemporaryFile(suffix=".toml", delete=False)
toml_path = Path(_toml_tmp.name)
_toml_tmp.close()
write_toml(toml_path)
atexit.register(toml_path.unlink, missing_ok=True)

_yaml_tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
yaml_path = Path(_yaml_tmp.name)
_yaml_tmp.close()
write_yaml(yaml_path)
atexit.register(yaml_path.unlink, missing_ok=True)

_dotenv_tmp = tempfile.NamedTemporaryFile(suffix=".env", delete=False)
dotenv_path = Path(_dotenv_tmp.name)
_dotenv_tmp.close()
write_dotenv(dotenv_path)
atexit.register(dotenv_path.unlink, missing_ok=True)

# hydra needs a directory with the config file named "config.yaml"
_hydra_dir = Path(tempfile.mkdtemp())
(_hydra_dir / "config.yaml").write_text(yaml_path.read_text())
atexit.register(shutil.rmtree, str(_hydra_dir), True)

# ── dature sources ────────────────────────────────────────────────────────────

_env_source = dature.EnvSource(prefix="BENCH_")
_json_source = dature.JsonSource(file=json_path)
_toml_source = dature.Toml10Source(file=toml_path)
_yaml_source = dature.Yaml12Source(file=yaml_path)
_dotenv_source = dature.EnvFileSource(file=dotenv_path)

# pre-warmed decorator objects (cache=False, one per source type)
_DatureEnv = dature.load(_env_source, cache=False)(BenchConfig)
_DatureJson = dature.load(_json_source, cache=False)(BenchConfig)
_DatureToml = dature.load(_toml_source, cache=False)(BenchConfig)
_DatureYaml = dature.load(_yaml_source, cache=False)(BenchConfig)
_DatureDotenv = dature.load(_dotenv_source, cache=False)(BenchConfig)
_DatureMulti = dature.load(_json_source, _env_source, cache=False, strategy="last_wins")(BenchConfig)

# Loader reuse — one Loader per source type, .load() called repeatedly
_LoaderEnv = Loader(_env_source, schema=BenchConfig, cache=False)
_LoaderJson = Loader(_json_source, schema=BenchConfig, cache=False)
_LoaderToml = Loader(_toml_source, schema=BenchConfig, cache=False)
_LoaderYaml = Loader(_yaml_source, schema=BenchConfig, cache=False)
_LoaderDotenv = Loader(_dotenv_source, schema=BenchConfig, cache=False)
_LoaderMulti = Loader(_json_source, _env_source, schema=BenchConfig, cache=False, strategy="last_wins")

# caching variants (all on EnvSource)
_DatureCacheNone = dature.load(_env_source, cache=False)(BenchConfig)
_DatureCacheEternal = dature.load(_env_source, cache=True)(BenchConfig)
_DatureCacheTTL = dature.load(_env_source, cache=timedelta(minutes=5))(BenchConfig)

# python-decouple env-file reader
_decouple_cfg = DecoupleConfig(RepositoryEnv(str(dotenv_path)))

# dynaconf multi-source (pre-configured at module level)
_dynaconf_multi = Dynaconf(
    settings_files=[str(json_path)],
    envvar_prefix="BENCH",
    environments=False,
    load_dotenv=False,
)

# ── pydantic-settings classes ─────────────────────────────────────────────────


class _PydanticEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BENCH_", env_file=None)
    host: str
    port: int
    debug: bool
    max_connections: int
    timeout: float
    db_name: str
    workers: int
    log_level: str


class _PydanticJson(BaseSettings):
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
        return (JsonConfigSettingsSource(settings_cls, json_file=str(json_path)),)


class _PydanticToml(BaseSettings):
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
        return (TomlConfigSettingsSource(settings_cls, toml_file=str(toml_path)),)


class _PydanticYaml(BaseSettings):
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
        return (YamlConfigSettingsSource(settings_cls, yaml_file=str(yaml_path)),)


class _PydanticDotenv(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(dotenv_path))
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
        return (dotenv_settings,)


class _PydanticMulti(BaseSettings):
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
        return (env_settings, JsonConfigSettingsSource(settings_cls, json_file=str(json_path)))


# ── load functions ────────────────────────────────────────────────────────────


# ENV
def dature_env_func() -> BenchConfig:
    return dature.load(_env_source, schema=BenchConfig)


def dature_env_hot() -> BenchConfig:
    return _DatureEnv()


def dature_env_loader() -> BenchConfig:
    return _LoaderEnv.load()


def dature_env_startup():
    dature.load(_env_source, cache=False)(BenchConfig)


def pydantic_env() -> _PydanticEnv:
    return _PydanticEnv()


def decouple_env() -> BenchConfig:
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


def dynaconf_env() -> BenchConfig:
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


# JSON
def dature_json_func() -> BenchConfig:
    return dature.load(_json_source, schema=BenchConfig)


def dature_json_hot() -> BenchConfig:
    return _DatureJson()


def dature_json_loader() -> BenchConfig:
    return _LoaderJson.load()


def dature_json_startup():
    dature.load(_json_source, cache=False)(BenchConfig)


def pydantic_json() -> _PydanticJson:
    return _PydanticJson()


def dynaconf_json() -> BenchConfig:
    settings = Dynaconf(settings_files=[str(json_path)], environments=False)
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


# TOML
def dature_toml_func() -> BenchConfig:
    return dature.load(_toml_source, schema=BenchConfig)


def dature_toml_hot() -> BenchConfig:
    return _DatureToml()


def dature_toml_loader() -> BenchConfig:
    return _LoaderToml.load()


def dature_toml_startup():
    dature.load(_toml_source, cache=False)(BenchConfig)


def pydantic_toml() -> _PydanticToml:
    return _PydanticToml()


def dynaconf_toml() -> BenchConfig:
    settings = Dynaconf(settings_files=[str(toml_path)], environments=False)
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


# YAML
def dature_yaml_func() -> BenchConfig:
    return dature.load(_yaml_source, schema=BenchConfig)


def dature_yaml_hot() -> BenchConfig:
    return _DatureYaml()


def dature_yaml_loader() -> BenchConfig:
    return _LoaderYaml.load()


def dature_yaml_startup():
    dature.load(_yaml_source, cache=False)(BenchConfig)


def pydantic_yaml() -> _PydanticYaml:
    return _PydanticYaml()


def dynaconf_yaml() -> BenchConfig:
    settings = Dynaconf(settings_files=[str(yaml_path)], environments=False)
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


def hydra_yaml():
    with initialize_config_dir(config_dir=str(_hydra_dir), job_name="benchmark", version_base=None):
        return compose(config_name="config")


# .env file
def dature_dotenv_func() -> BenchConfig:
    return dature.load(_dotenv_source, schema=BenchConfig)


def dature_dotenv_hot() -> BenchConfig:
    return _DatureDotenv()


def dature_dotenv_loader() -> BenchConfig:
    return _LoaderDotenv.load()


def dature_dotenv_startup():
    dature.load(_dotenv_source, cache=False)(BenchConfig)


def pydantic_dotenv() -> _PydanticDotenv:
    return _PydanticDotenv()


def decouple_dotenv() -> BenchConfig:
    return BenchConfig(
        host=_decouple_cfg("HOST"),
        port=_decouple_cfg("PORT", cast=int),
        debug=_decouple_cfg("DEBUG", cast=bool),
        max_connections=_decouple_cfg("MAX_CONNECTIONS", cast=int),
        timeout=_decouple_cfg("TIMEOUT", cast=float),
        db_name=_decouple_cfg("DB_NAME"),
        workers=_decouple_cfg("WORKERS", cast=int),
        log_level=_decouple_cfg("LOG_LEVEL"),
    )


def dynaconf_dotenv() -> BenchConfig:
    settings = Dynaconf(
        environments=False, load_dotenv=True, DOTENV_PATH_FOR_DYNACONF=str(dotenv_path), envvar_prefix=False
    )
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


# Multi-source
def dature_multi_func() -> BenchConfig:
    return dature.load(_json_source, _env_source, schema=BenchConfig, strategy="last_wins")


def dature_multi_hot() -> BenchConfig:
    return _DatureMulti()


def dature_multi_loader() -> BenchConfig:
    return _LoaderMulti.load()


def dature_multi_startup():
    dature.load(_json_source, _env_source, cache=False, strategy="last_wins")(BenchConfig)


def pydantic_multi() -> _PydanticMulti:
    return _PydanticMulti()


def dynaconf_multi() -> BenchConfig:
    _dynaconf_multi.reload()
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


# Caching
def dature_cache_none() -> BenchConfig:
    return _DatureCacheNone()


def dature_cache_eternal() -> BenchConfig:
    return _DatureCacheEternal()


def dature_cache_ttl() -> BenchConfig:
    return _DatureCacheTTL()


@functools.lru_cache(maxsize=1)
def _pydantic_once() -> _PydanticEnv:
    return _PydanticEnv()


def pydantic_cached() -> _PydanticEnv:
    return _pydantic_once()


@functools.lru_cache(maxsize=1)
def _decouple_once() -> BenchConfig:
    return decouple_env()


def decouple_cached() -> BenchConfig:
    return _decouple_once()


@functools.lru_cache(maxsize=1)
def _dynaconf_once() -> BenchConfig:
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


def dynaconf_cached() -> BenchConfig:
    return _dynaconf_once()
