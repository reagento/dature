"""Full-cycle examples: model declaration + source + loader + load, one call = one cycle.

Each function builds everything from scratch (no reused loader) and returns the loaded
config. Run in-process through ``run_bench`` / ``run_mem_bench``; the library import is a
one-time cost measured separately (``bench_import.py``), not here — the first call warms
``sys.modules`` so subsequent timed calls capture only build + load.

Imports are kept inside each function so a function is self-contained and only pulls the
library it needs; after warmup the repeated ``import`` is a cached no-op. Config values and
file paths come from the environment (set by the runner via ``prepare`` + ``set_env_vars``).
"""
# Imports live inside functions (self-contained examples), so PLC0415 is disabled here.
# ruff: noqa: PLC0415

import os

# ── ENV source ─────────────────────────────────────────────────────────────────


def dature_env():
    from dataclasses import dataclass

    import dature
    from dature import EnvSource

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return dature.load(EnvSource(prefix="BENCH_"), schema=Cfg)


def pydantic_env():
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class S(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="BENCH_")
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return S()


def decouple_env():
    from dataclasses import dataclass

    from decouple import config

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg(
        host=config("BENCH_HOST"),
        port=config("BENCH_PORT", cast=int),
        debug=config("BENCH_DEBUG", cast=bool),
        max_connections=config("BENCH_MAX_CONNECTIONS", cast=int),
        timeout=config("BENCH_TIMEOUT", cast=float),
        db_name=config("BENCH_DB_NAME"),
        workers=config("BENCH_WORKERS", cast=int),
        log_level=config("BENCH_LOG_LEVEL"),
    )


def dynaconf_env():
    from dataclasses import dataclass

    from dynaconf import Dynaconf

    settings = Dynaconf(envvar_prefix="BENCH", environments=False, load_dotenv=False)

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg(
        host=settings.HOST,
        port=int(settings.PORT),
        debug=bool(settings.DEBUG),
        max_connections=int(settings.MAX_CONNECTIONS),
        timeout=float(settings.TIMEOUT),
        db_name=settings.DB_NAME,
        workers=int(settings.WORKERS),
        log_level=settings.LOG_LEVEL,
    )


# ── JSON file ────────────────────────────────────────────────────────────────


def dature_json():
    from dataclasses import dataclass
    from pathlib import Path

    import dature
    from dature import JsonSource

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return dature.load(JsonSource(file=Path(os.environ["BENCH_JSON_PATH"])), schema=Cfg)


def pydantic_json():
    from pydantic_settings import BaseSettings, JsonConfigSettingsSource

    path = os.environ["BENCH_JSON_PATH"]

    class S(BaseSettings):
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
            return (JsonConfigSettingsSource(settings_cls, json_file=path),)

    return S()


def dynaconf_json():
    from dataclasses import dataclass

    from dynaconf import Dynaconf

    settings = Dynaconf(settings_files=[os.environ["BENCH_JSON_PATH"]], environments=False)

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg(
        host=settings.HOST,
        port=int(settings.PORT),
        debug=bool(settings.DEBUG),
        max_connections=int(settings.MAX_CONNECTIONS),
        timeout=float(settings.TIMEOUT),
        db_name=settings.DB_NAME,
        workers=int(settings.WORKERS),
        log_level=settings.LOG_LEVEL,
    )


# ── TOML file ────────────────────────────────────────────────────────────────


def dature_toml():
    from dataclasses import dataclass
    from pathlib import Path

    import dature
    from dature import Toml10Source

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return dature.load(Toml10Source(file=Path(os.environ["BENCH_TOML_PATH"])), schema=Cfg)


def pydantic_toml():
    from pydantic_settings import BaseSettings, TomlConfigSettingsSource

    path = os.environ["BENCH_TOML_PATH"]

    class S(BaseSettings):
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
            return (TomlConfigSettingsSource(settings_cls, toml_file=path),)

    return S()


def dynaconf_toml():
    from dataclasses import dataclass

    from dynaconf import Dynaconf

    settings = Dynaconf(settings_files=[os.environ["BENCH_TOML_PATH"]], environments=False)

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg(
        host=settings.HOST,
        port=int(settings.PORT),
        debug=bool(settings.DEBUG),
        max_connections=int(settings.MAX_CONNECTIONS),
        timeout=float(settings.TIMEOUT),
        db_name=settings.DB_NAME,
        workers=int(settings.WORKERS),
        log_level=settings.LOG_LEVEL,
    )


# ── YAML file ────────────────────────────────────────────────────────────────


def dature_yaml():
    from dataclasses import dataclass
    from pathlib import Path

    import dature
    from dature import Yaml12Source

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return dature.load(Yaml12Source(file=Path(os.environ["BENCH_YAML_PATH"])), schema=Cfg)


def pydantic_yaml():
    from pydantic_settings import BaseSettings, YamlConfigSettingsSource

    path = os.environ["BENCH_YAML_PATH"]

    class S(BaseSettings):
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
            return (YamlConfigSettingsSource(settings_cls, yaml_file=path),)

    return S()


def dynaconf_yaml():
    from dataclasses import dataclass

    from dynaconf import Dynaconf

    settings = Dynaconf(settings_files=[os.environ["BENCH_YAML_PATH"]], environments=False)

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg(
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
    from hydra import compose, initialize_config_dir

    # Fresh subprocess → clean GlobalHydra singleton, no reset needed.
    with initialize_config_dir(config_dir=os.environ["BENCH_HYDRA_DIR"], job_name="bench", version_base=None):
        return compose(config_name="config")


# ── .env file ────────────────────────────────────────────────────────────────


def dature_dotenv():
    from dataclasses import dataclass
    from pathlib import Path

    import dature
    from dature import EnvFileSource

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return dature.load(EnvFileSource(file=Path(os.environ["BENCH_DOTENV_PATH"])), schema=Cfg)


def pydantic_dotenv():
    from pydantic_settings import BaseSettings, SettingsConfigDict

    path = os.environ["BENCH_DOTENV_PATH"]

    class S(BaseSettings):
        model_config = SettingsConfigDict(env_file=path)
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

    return S()


def decouple_dotenv():
    from dataclasses import dataclass

    from decouple import Config, RepositoryEnv

    cfg = Config(RepositoryEnv(os.environ["BENCH_DOTENV_PATH"]))

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg(
        host=cfg("HOST"),
        port=cfg("PORT", cast=int),
        debug=cfg("DEBUG", cast=bool),
        max_connections=cfg("MAX_CONNECTIONS", cast=int),
        timeout=cfg("TIMEOUT", cast=float),
        db_name=cfg("DB_NAME"),
        workers=cfg("WORKERS", cast=int),
        log_level=cfg("LOG_LEVEL"),
    )


def dynaconf_dotenv():
    from dataclasses import dataclass

    from dynaconf import Dynaconf

    settings = Dynaconf(
        environments=False,
        load_dotenv=True,
        DOTENV_PATH_FOR_DYNACONF=os.environ["BENCH_DOTENV_PATH"],
        envvar_prefix=False,
    )

    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg(
        host=settings.HOST,
        port=int(settings.PORT),
        debug=bool(settings.DEBUG),
        max_connections=int(settings.MAX_CONNECTIONS),
        timeout=float(settings.TIMEOUT),
        db_name=settings.DB_NAME,
        workers=int(settings.WORKERS),
        log_level=settings.LOG_LEVEL,
    )


# ── Nested model, five levels deep (ENV source) ────────────────────────────────


def dature_nested():
    from dataclasses import dataclass

    import dature
    from dature import EnvSource

    @dataclass
    class L5:
        value: str
        count: int

    @dataclass
    class L4:
        inner: L5
        value: str

    @dataclass
    class L3:
        inner: L4
        value: str

    @dataclass
    class L2:
        inner: L3
        value: str

    @dataclass
    class L1:
        inner: L2
        value: str
        debug: bool

    return dature.load(EnvSource(prefix="BENCH_ND_"), schema=L1)


def pydantic_nested():
    from pydantic import BaseModel
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class M5(BaseModel):
        value: str
        count: int

    class M4(BaseModel):
        inner: M5
        value: str

    class M3(BaseModel):
        inner: M4
        value: str

    class M2(BaseModel):
        inner: M3
        value: str

    class S(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="BENCH_ND_", env_nested_delimiter="__")
        inner: M2
        value: str
        debug: bool

    return S()


# ── Three independent models loaded at once (ENV source) ───────────────────────


def dature_multi_model():
    from dataclasses import dataclass

    import dature
    from dature import EnvSource

    @dataclass
    class CA:
        field1: str
        field2: int
        field3: bool

    @dataclass
    class CB:
        field1: str
        field2: int
        field3: bool

    @dataclass
    class CC:
        field1: str
        field2: int
        field3: bool

    return (
        dature.load(EnvSource(prefix="BENCH_A_"), schema=CA),
        dature.load(EnvSource(prefix="BENCH_B_"), schema=CB),
        dature.load(EnvSource(prefix="BENCH_C_"), schema=CC),
    )


def pydantic_multi_model():
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class SA(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="BENCH_A_")
        field1: str
        field2: int
        field3: bool

    class SB(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="BENCH_B_")
        field1: str
        field2: int
        field3: bool

    class SC(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="BENCH_C_")
        field1: str
        field2: int
        field3: bool

    return SA(), SB(), SC()


def dynaconf_multi_model():
    from dataclasses import dataclass

    from dynaconf import Dynaconf

    @dataclass
    class C:
        field1: str
        field2: int
        field3: bool

    def build(prefix: str) -> C:
        s = Dynaconf(envvar_prefix=prefix, environments=False, load_dotenv=False)
        return C(field1=s.FIELD1, field2=int(s.FIELD2), field3=bool(s.FIELD3))

    return build("BENCH_A"), build("BENCH_B"), build("BENCH_C")


# ── dature decorator-mode variants ─────────────────────────────────────────────
# The functions above use function mode — dature.load(source, schema=Cfg). These use
# decorator mode — @dature.load(source)(Cfg) then Cfg() — the other public entry point.


def dature_env_dec():
    from dataclasses import dataclass

    import dature
    from dature import EnvSource

    @dature.load(EnvSource(prefix="BENCH_"), cache=False)
    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg()


def dature_env_dec_warm():
    """Same as ``dature_env_dec`` but with ``cache_engine=True`` — the compiled retort is
    retained for the class lifetime instead of being rebuilt (and discarded) on every load.
    Contrast the retained RSS of this against ``dature_env_dec`` to see what cache_engine buys.
    """
    from dataclasses import dataclass

    import dature
    from dature import EnvSource

    @dature.load(EnvSource(prefix="BENCH_"), cache=False, cache_engine=True)
    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg()


def dature_dotenv_dec():
    from dataclasses import dataclass
    from pathlib import Path

    import dature
    from dature import EnvFileSource

    @dature.load(EnvFileSource(file=Path(os.environ["BENCH_DOTENV_PATH"])), cache=False)
    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg()


def dature_json_dec():
    from dataclasses import dataclass
    from pathlib import Path

    import dature
    from dature import JsonSource

    @dature.load(JsonSource(file=Path(os.environ["BENCH_JSON_PATH"])), cache=False)
    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg()


def dature_toml_dec():
    from dataclasses import dataclass
    from pathlib import Path

    import dature
    from dature import Toml10Source

    @dature.load(Toml10Source(file=Path(os.environ["BENCH_TOML_PATH"])), cache=False)
    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg()


def dature_yaml_dec():
    from dataclasses import dataclass
    from pathlib import Path

    import dature
    from dature import Yaml12Source

    @dature.load(Yaml12Source(file=Path(os.environ["BENCH_YAML_PATH"])), cache=False)
    @dataclass
    class Cfg:
        host: str
        port: int
        debug: bool
        max_connections: int
        timeout: float
        db_name: str
        workers: int
        log_level: str

    return Cfg()


def dature_nested_dec():
    from dataclasses import dataclass

    import dature
    from dature import EnvSource

    @dataclass
    class L5:
        value: str
        count: int

    @dataclass
    class L4:
        inner: L5
        value: str

    @dataclass
    class L3:
        inner: L4
        value: str

    @dataclass
    class L2:
        inner: L3
        value: str

    @dature.load(EnvSource(prefix="BENCH_ND_"), cache=False)
    @dataclass
    class L1:
        inner: L2
        value: str
        debug: bool

    return L1()


def dature_multi_model_dec():
    from dataclasses import dataclass

    import dature
    from dature import EnvSource

    @dature.load(EnvSource(prefix="BENCH_A_"), cache=False)
    @dataclass
    class CA:
        field1: str
        field2: int
        field3: bool

    @dature.load(EnvSource(prefix="BENCH_B_"), cache=False)
    @dataclass
    class CB:
        field1: str
        field2: int
        field3: bool

    @dature.load(EnvSource(prefix="BENCH_C_"), cache=False)
    @dataclass
    class CC:
        field1: str
        field2: int
        field3: bool

    return CA(), CB(), CC()
