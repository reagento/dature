"""YAML file loading benchmark: dature vs pydantic-settings vs dynaconf vs hydra.

dature uses Yaml12Source (ruamel.yaml).
hydra is included for YAML only — it returns OmegaConf DictConfig, not a typed dataclass.
Hydra benchmark includes GlobalHydra singleton reset overhead (unavoidable for repeated
calls in a tight loop; in production hydra is initialized once).

python-decouple: no YAML file support — excluded.

Run: uv run --group benchmarks python benchmarks/bench_file_yaml.py
"""

import atexit
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BenchConfig, print_table, run_bench, write_yaml
from dynaconf import Dynaconf
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from pydantic_settings import BaseSettings, YamlConfigSettingsSource

import dature

# --- temp file/dir setup ---
_tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
yaml_path = Path(_tmp.name)
_tmp.close()
write_yaml(yaml_path)
atexit.register(yaml_path.unlink, missing_ok=True)

# hydra needs a directory with the config file named "config.yaml"
_hydra_dir = Path(tempfile.mkdtemp())
(_hydra_dir / "config.yaml").write_text(yaml_path.read_text())
atexit.register(shutil.rmtree, str(_hydra_dir), True)

_yaml_source = dature.Yaml12Source(file=yaml_path)
_DatureDecorated = dature.load(_yaml_source, cache=False)(BenchConfig)


class _PydanticYamlSettings(BaseSettings):
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


def dature_load() -> BenchConfig:
    return dature.load(_yaml_source, schema=BenchConfig)


def dature_decorator_hot() -> BenchConfig:
    return _DatureDecorated()


def dature_decorator_startup():
    dature.load(_yaml_source, cache=False)(BenchConfig)


def pydantic_load() -> _PydanticYamlSettings:
    return _PydanticYamlSettings()


def dynaconf_load() -> BenchConfig:
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


def hydra_load():
    # GlobalHydra must be cleared between calls; context manager handles cleanup on exit
    with initialize_config_dir(config_dir=str(_hydra_dir), job_name="benchmark", version_base=None):
        return compose(config_name="config")


if __name__ == "__main__":
    GlobalHydra.instance().clear()  # ensure clean state before first hydra call

    results = [
        ("dature (func mode)", *run_bench(dature_load)),
        ("dature (decorator, hot)", *run_bench(dature_decorator_hot)),
        ("pydantic-settings", *run_bench(pydantic_load)),
        ("dynaconf", *run_bench(dynaconf_load)),
        ("hydra (DictConfig, not typed)", *run_bench(hydra_load)),
    ]
    print_table("YAML file loading  (8 fields, file → typed dataclass / DictConfig)", results)
    print("  Note: python-decouple excluded (no YAML file support)")
    print("  Note: hydra result is OmegaConf DictConfig, includes singleton reset overhead")

    startup = [("dature (decorator, startup)", *run_bench(dature_decorator_startup))]
    print_table("dature decorator — one-time startup cost", startup)
