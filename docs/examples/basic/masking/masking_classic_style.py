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


conf = dature.Dature(
    masking={"mask": "*****", "visible_prefix": 2, "visible_suffix": 2},
)

config = conf.load(
    dature.Yaml12Source(file=SOURCES_DIR / "masking_by_name.yaml"),
    schema=Config,
)
assert (
    mask_value("my_secret_password", masking=conf.config.masking) == "my*****rd"
)
assert mask_value("ab", masking=conf.config.masking) == "ab"
# --8<-- [end:example]
