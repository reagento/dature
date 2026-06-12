from pathlib import Path
SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
import os
import sys
import tempfile
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int


with tempfile.TemporaryDirectory() as tmp:
    config_dir = Path(tmp)
    (config_dir / "app.yaml").write_text(
        (SHARED_DIR / "common_app.yaml").read_text(),
    )

    os.environ["APPDATA" if sys.platform == "win32" else "XDG_CONFIG_HOME"] = (
        str(config_dir)
    )

    config = dature.load(
        dature.Yaml12Source(file="app.yaml"),
        schema=Config,
    )

    assert config.host == "localhost"
    assert config.port == 8080
# --8<-- [end:example]
