"""TOML file loading benchmark: dature vs pydantic-settings vs dynaconf.

dature uses Toml10Source (requires dature[toml] / toml-rs package).
pydantic-settings uses TomlConfigSettingsSource (built-in on Python 3.12+).

python-decouple: no TOML file support — excluded.
hydra: YAML-only — excluded.

Run: uv run --group benchmarks python benchmarks/bench_file_toml.py
"""

import atexit
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BenchConfig, print_table, run_bench, write_toml
from dynaconf import Dynaconf
from pydantic_settings import BaseSettings, TomlConfigSettingsSource

import dature

# --- temp file setup ---
_tmp = tempfile.NamedTemporaryFile(suffix=".toml", delete=False)
toml_path = Path(_tmp.name)
_tmp.close()
write_toml(toml_path)
atexit.register(toml_path.unlink, missing_ok=True)

_toml_source = dature.Toml10Source(file=toml_path)
_DatureDecorated = dature.load(_toml_source, cache=False)(BenchConfig)


class _PydanticTomlSettings(BaseSettings):
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


def dature_load() -> BenchConfig:
    return dature.load(_toml_source, schema=BenchConfig)


def dature_decorator_hot() -> BenchConfig:
    return _DatureDecorated()


def dature_decorator_startup():
    dature.load(_toml_source, cache=False)(BenchConfig)


def pydantic_load() -> _PydanticTomlSettings:
    return _PydanticTomlSettings()


def dynaconf_load() -> BenchConfig:
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


if __name__ == "__main__":
    results = [
        ("dature (func mode)", *run_bench(dature_load)),
        ("dature (decorator, hot)", *run_bench(dature_decorator_hot)),
        ("pydantic-settings", *run_bench(pydantic_load)),
        ("dynaconf", *run_bench(dynaconf_load)),
    ]
    print_table("TOML file loading  (8 fields, file → typed dataclass)", results)
    print("  Note: python-decouple excluded (no TOML file support)")
    print("  Note: hydra excluded (YAML only)")

    startup = [("dature (decorator, startup)", *run_bench(dature_decorator_startup))]
    print_table("dature decorator — one-time startup cost", startup)
