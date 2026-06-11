import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    debug: bool = True
    name: str = "default"


with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    config_file = tmpdir_path / "config.yaml"
    config_file.write_text((SHARED_DIR / "common_app.yaml").read_text())

    dature.configure(
        loading={
            "search_system_paths": False,
            "system_config_dirs": (tmpdir_path,),
        },
    )

    dature.load(
        dature.Yaml12Source(file="config.yaml"),
        schema=Config,
    )  # Failed