"""Example 3: Disable system path search globally

demonstrates error when file not found."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    debug: bool = True
    name: str = "default"


# Create temp directory with config file
with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    config_file = tmpdir_path / "config.yaml"
    config_file.write_text((SHARED_DIR / "common_app.yaml").read_text())

    # Disable system search globally,
    # even though config exists in system_config_dirs
    dature.configure(
        loading={
            "search_system_paths": False,
            "system_config_dirs": (tmpdir_path,),
        },
    )

    # This will fail because search_system_paths=False
    # prevents searching in system_config_dirs
    config = dature.load(
        dature.Yaml12Source(file="config.yaml"),
        schema=Config,
    )
