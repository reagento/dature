from pathlib import Path
SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
import tempfile
from dataclasses import dataclass

import dature


@dataclass
class Config:
    name: str
    value: int


with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    config_file = tmpdir_path / "local.yaml"
    config_file.write_text((SHARED_DIR / "common_app.yaml").read_text())

    dature.load(
        dature.Yaml12Source(
            file="local.yaml",
            system_config_dirs=(tmpdir_path,),
            search_system_paths=False,
        ),
        schema=Config,
    )
# --8<-- [end:example]
