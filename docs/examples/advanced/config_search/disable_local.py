"""Example 4: Disable system path search for a specific source."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    name: str
    value: int


with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    config_file = tmpdir_path / "local.yaml"
    config_file.write_text((SHARED_DIR / "common_app.yaml").read_text())

    # Disable search only for this source (global setting remains unchanged)
    # Even though system_config_dirs has the file, it won't be searched
    config = dature.load(
        dature.Yaml12Source(
            file="local.yaml",
            system_config_dirs=(tmpdir_path,),
            search_system_paths=False,
        ),
        schema=Config,
    )
