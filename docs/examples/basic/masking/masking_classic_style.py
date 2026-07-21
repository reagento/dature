from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature
from dature.masking.masking import mask_value


@dataclass
class Config:
    password: str
    host: str


dature.configure(
    masking={"mask": "*****", "visible_prefix": 2, "visible_suffix": 2},
)

config = dature.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_by_name.yaml"),
    schema=Config,
)
assert mask_value("my_secret_password") == "my*****rd"
assert mask_value("ab") == "ab"
# --8<-- [end:example]
