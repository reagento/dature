"""ENV file (.env) loading benchmark: dature vs pydantic-settings vs python-decouple vs dynaconf.

Each library reads a .env file (KEY=VALUE format) into a typed dataclass.
The .env file uses plain field names (HOST, PORT, …) without any prefix.

dynaconf: uses load_dotenv=True + DOTENV_PATH_FOR_DYNACONF + envvar_prefix=False.
hydra: no .env file support — excluded.

Run: uv run --group benchmarks python benchmarks/bench_file_env.py
"""

import atexit
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BenchConfig, print_table, run_bench, write_dotenv
from decouple import Config as DecoupleConfig
from decouple import RepositoryEnv
from dynaconf import Dynaconf
from pydantic_settings import BaseSettings, SettingsConfigDict

import dature

# --- temp file setup ---
_tmp = tempfile.NamedTemporaryFile(suffix=".env", delete=False)
env_path = Path(_tmp.name)
_tmp.close()
write_dotenv(env_path)
atexit.register(env_path.unlink, missing_ok=True)

_env_source = dature.EnvFileSource(file=env_path)
_DatureDecorated = dature.load(_env_source, cache=False)(BenchConfig)
_decouple_cfg = DecoupleConfig(RepositoryEnv(str(env_path)))


class _PydanticEnvFileSettings(BaseSettings):
    # dotenv_settings reads from env_file; settings_customise_sources skips OS env vars
    model_config = SettingsConfigDict(env_file=str(env_path))

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


def dature_load() -> BenchConfig:
    return dature.load(_env_source, schema=BenchConfig)


def dature_decorator_hot() -> BenchConfig:
    return _DatureDecorated()


def dature_decorator_startup():
    dature.load(_env_source, cache=False)(BenchConfig)


def pydantic_load() -> _PydanticEnvFileSettings:
    return _PydanticEnvFileSettings()


def decouple_load() -> BenchConfig:
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


def dynaconf_load() -> BenchConfig:
    settings = Dynaconf(
        environments=False,
        load_dotenv=True,
        DOTENV_PATH_FOR_DYNACONF=str(env_path),
        envvar_prefix=False,
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


if __name__ == "__main__":
    results = [
        ("dature (func mode)", *run_bench(dature_load)),
        ("dature (decorator, hot)", *run_bench(dature_decorator_hot)),
        ("pydantic-settings", *run_bench(pydantic_load)),
        ("python-decouple", *run_bench(decouple_load)),
        ("dynaconf", *run_bench(dynaconf_load)),
    ]
    print_table("ENV file (.env) loading  (8 fields, file → typed dataclass)", results)
    print("  Note: hydra excluded (no .env file support)")

    startup = [("dature (decorator, startup)", *run_bench(dature_decorator_startup))]
    print_table("dature decorator — one-time startup cost", startup)
