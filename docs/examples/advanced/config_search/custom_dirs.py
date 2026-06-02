"""Example 2: Custom system directories for config search."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int


with tempfile.TemporaryDirectory() as tmpdir:
    custom_dir = Path(tmpdir)

    config_file = custom_dir / "app.yaml"
    config_file.write_text((SHARED_DIR / "common_app.yaml").read_text())

    # Searches: ./app.yaml -> custom_dir/app.yaml (found!)
    config = dature.load(
        dature.Yaml12Source(
            file="app.yaml",
            system_config_dirs=(custom_dir,),
        ),
        schema=Config,
    )

    assert config.host == "localhost"
    assert config.port == 8080
