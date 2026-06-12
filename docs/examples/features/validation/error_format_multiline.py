from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Config:
    tags: Annotated[list[str], V.unique_items()]


dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "error_format_multiline.yaml"),
    schema=Config,
)
# --8<-- [end:example]