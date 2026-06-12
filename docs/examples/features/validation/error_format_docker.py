from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass
from typing import Annotated

import dature
from dature import V


@dataclass
class Config:
    port: Annotated[int, V >= 1]

dature.load(
    dature.DockerSecretsSource(dir_=SOURCES_DIR / "error_format_docker"),
    schema=Config,
)
# --8<-- [end:example]
