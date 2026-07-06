"""JSON file loading benchmark: dature vs pydantic-settings vs dynaconf.

python-decouple: no JSON file support — excluded.
hydra: YAML-only — excluded.

Run: uv run --group benchmarks python benchmarks/bench_file_json.py
"""

import atexit
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BenchConfig, print_table, run_bench, write_json
from dynaconf import Dynaconf
from pydantic_settings import BaseSettings, JsonConfigSettingsSource

import dature

# --- temp file setup ---
_tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
json_path = Path(_tmp.name)
_tmp.close()
write_json(json_path)
atexit.register(json_path.unlink, missing_ok=True)

_json_source = dature.JsonSource(file=json_path)
_DatureDecorated = dature.load(_json_source, cache=False)(BenchConfig)


class _PydanticJsonSettings(BaseSettings):
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


def dature_load() -> BenchConfig:
    return dature.load(_json_source, schema=BenchConfig)


def dature_decorator_hot() -> BenchConfig:
    return _DatureDecorated()


def dature_decorator_startup():
    dature.load(_json_source, cache=False)(BenchConfig)


def pydantic_load() -> _PydanticJsonSettings:
    return _PydanticJsonSettings()


def dynaconf_load() -> BenchConfig:
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


if __name__ == "__main__":
    results = [
        ("dature (func mode)", *run_bench(dature_load)),
        ("dature (decorator, hot)", *run_bench(dature_decorator_hot)),
        ("pydantic-settings", *run_bench(pydantic_load)),
        ("dynaconf", *run_bench(dynaconf_load)),
    ]
    print_table("JSON file loading  (8 fields, file → typed dataclass)", results)
    print("  Note: python-decouple excluded (no JSON file support)")
    print("  Note: hydra excluded (YAML only)")

    startup = [("dature (decorator, startup)", *run_bench(dature_decorator_startup))]
    print_table("dature decorator — one-time startup cost", startup)
