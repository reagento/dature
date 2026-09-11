# --8<-- [start:example]
import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature


@dataclass
class Config:
    host: str
    port: int


with tempfile.TemporaryDirectory() as tmpdir:
    custom_dir = Path(tmpdir)

    config_file = custom_dir / "app.env"
    config_file.write_text("HOST=localhost\nPORT=8080\n")

    config = dature.load(
        dature.EnvFileSource(
            file="app.env",
            config_dirs=custom_dir,
        ),
        schema=Config,
    )

    assert config.host == "localhost"
    assert config.port == 8080
# --8<-- [end:example]
