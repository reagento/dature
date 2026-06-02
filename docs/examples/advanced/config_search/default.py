"""Example 1: Default behavior - system path search enabled by default."""

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int


with tempfile.TemporaryDirectory() as tmp:
    config_dir = Path(tmp)
    (config_dir / "app.yaml").write_text(
        (SHARED_DIR / "common_app.yaml").read_text(),
    )

    # Redirect the platform-appropriate env var so search lands in our temp dir
    # instead of the real user config location.
    os.environ["APPDATA" if sys.platform == "win32" else "XDG_CONFIG_HOME"] = (
        str(config_dir)
    )

    config = dature.load(
        dature.Yaml12Source(file="app.yaml"),
        schema=Config,
    )

    assert config.host == "localhost"
    assert config.port == 8080
