"""Classic ab*****cd masking style via dature.configure()."""

from dataclasses import dataclass
from pathlib import Path

import dature
from dature.masking.masking import mask_value

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:classic-style]
dature.configure(masking={"mask": "*****", "visible_prefix": 2, "visible_suffix": 2})
# "my_secret_password" → "my*****rd"
# "ab"                 → "ab"  (too short — shown as-is)
# --8<-- [end:classic-style]


@dataclass
class Config:
    password: str
    host: str


config = dature.load(dature.Source(file=SOURCES_DIR / "masking_by_name.yaml"), schema=Config)
assert mask_value("my_secret_password") == "my*****rd"
assert mask_value("ab") == "ab"

dature.configure(masking={})
