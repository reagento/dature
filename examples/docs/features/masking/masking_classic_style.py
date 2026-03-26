"""Classic ab*****cd masking style via configure()."""

from dataclasses import dataclass
from pathlib import Path

from dature import Source, configure, load
from dature.config import MaskingConfig
from dature.masking.masking import mask_value

SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:classic-style]
configure(masking=MaskingConfig(mask="*****", visible_prefix=2, visible_suffix=2))
# "my_secret_password" → "my*****rd"
# "ab"                 → "ab"  (too short — shown as-is)
# --8<-- [end:classic-style]


@dataclass
class Config:
    password: str
    host: str


config = load(Source(file_=SOURCES_DIR / "masking_by_name.yaml"), Config)
assert mask_value("my_secret_password") == "my*****rd"
assert mask_value("ab") == "ab"

configure(masking=MaskingConfig())
