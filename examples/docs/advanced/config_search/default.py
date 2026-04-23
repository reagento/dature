"""Example 1: Default behavior - system path search enabled by default."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature
from dature.config_paths import get_system_config_dirs

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int


# Get first system config dir (platform-specific: ~/.config, %APPDATA%, etc.)
config_dir = next(get_system_config_dirs())
config_dir.mkdir(parents=True, exist_ok=True)

with tempfile.NamedTemporaryFile(
    mode="w",
    dir=config_dir,
    suffix=".yaml",
    delete=True,
) as temp_file:
    temp_file.write((SHARED_DIR / "common_app.yaml").read_text())
    temp_file.flush()

    config = dature.load(
        dature.Yaml12Source(file=Path(temp_file.name).name),
        schema=Config,
    )

    assert config.host == "localhost"
    assert config.port == 8080
