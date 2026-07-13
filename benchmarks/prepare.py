"""Fixture setup for the benchmark runners.

Writes temp config files (JSON/TOML/YAML/.env + a hydra config dir) from BENCH_DATA and
exports their paths via environment variables, which the example functions read. Imported for
its side effects by bench_speed.py / bench_memory.py. Not meant to be run directly.
"""

import atexit
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _common import BENCH_ENV_VARS

# Typed values for file-based sources (JSON/TOML/YAML parse native types).
BENCH_DATA: dict = {
    "host": "localhost",
    "port": 5432,
    "debug": True,
    "max_connections": 100,
    "timeout": 30.5,
    "db_name": "mydb",
    "workers": 4,
    "log_level": "INFO",
}


def _write_json(path: Path) -> None:
    path.write_text(json.dumps(BENCH_DATA))


def _write_toml(path: Path) -> None:
    lines = []
    for k, v in BENCH_DATA.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, str):
            lines.append(f'{k} = "{v}"')
        else:
            lines.append(f"{k} = {v}")
    path.write_text("\n".join(lines) + "\n")


def _write_yaml(path: Path) -> None:
    lines = [f"{k}: {'true' if v else 'false'}" if isinstance(v, bool) else f"{k}: {v}" for k, v in BENCH_DATA.items()]
    path.write_text("\n".join(lines) + "\n")


def _write_dotenv(path: Path) -> None:
    lines = [f"{k[len('BENCH_') :]}={v}" for k, v in BENCH_ENV_VARS.items()]
    path.write_text("\n".join(lines) + "\n")


def _make_temp(suffix: str, writer) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    path = Path(tmp.name)
    tmp.close()
    writer(path)
    atexit.register(path.unlink, missing_ok=True)
    return path


json_path = _make_temp(".json", _write_json)
toml_path = _make_temp(".toml", _write_toml)
yaml_path = _make_temp(".yaml", _write_yaml)
dotenv_path = _make_temp(".env", _write_dotenv)

# hydra needs a directory containing a file named "config.yaml"
hydra_dir = Path(tempfile.mkdtemp())
(hydra_dir / "config.yaml").write_text(yaml_path.read_text())
atexit.register(shutil.rmtree, str(hydra_dir), True)

# Export paths so the example functions can read them from the environment.
os.environ["BENCH_JSON_PATH"] = str(json_path)
os.environ["BENCH_TOML_PATH"] = str(toml_path)
os.environ["BENCH_YAML_PATH"] = str(yaml_path)
os.environ["BENCH_DOTENV_PATH"] = str(dotenv_path)
os.environ["BENCH_HYDRA_DIR"] = str(hydra_dir)
