"""Merge mode masking — Source.secret_field_names combined with Merge."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from dature import Merge, Source, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.string import MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    api_key: Annotated[str, MinLength(value=20)] = ""


# --8<-- [start:merge-mode]
try:
    load(
        Merge(
            Source(file_=SOURCES_DIR / "masking_merge_mode_defaults.yaml"),
            Source(
                file_=SOURCES_DIR / "masking_merge_mode_secrets.yaml",
                secret_field_names=("api_key",),
            ),
        ),
        Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "masking_merge_mode_secrets.yaml")
    assert str(exc) == "Config loading errors (1)"
    assert str(exc.exceptions[0]) == (
        "  [api_key]  Value must have at least 20 characters\n"
        '   ├── api_key: "<REDACTED>"\n'
        "   │             ^^^^^^^^^^\n"
        f"   └── FILE '{source}', line 1"
    )
else:
    raise AssertionError("Expected DatureConfigError")
# --8<-- [end:merge-mode]
