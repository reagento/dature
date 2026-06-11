# --8<-- [start:setup]
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    tags: Annotated[list[str], V.unique_items()]

# --8<-- [end:setup]

# --8<-- [start:example]
dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "error_format_multiline.yaml"),
    schema=Config,
)
# --8<-- [end:example]
