from pathlib import Path
SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
import tempfile
from dataclasses import dataclass

import dature


@dataclass
class Config:
    host: str
    port: int


with tempfile.TemporaryDirectory() as tmpdir:
    custom_dir = Path(tmpdir)

    config_file = custom_dir / "app.yaml"
    config_file.write_text((SHARED_DIR / "common_app.yaml").read_text())

    config = dature.load(
        dature.Yaml12Source(
            file="app.yaml",
            system_config_dirs=(custom_dir,),
        ),
        schema=Config,
    )

    assert config.host == "localhost"
    assert config.port == 8080
# --8<-- [end:example]
