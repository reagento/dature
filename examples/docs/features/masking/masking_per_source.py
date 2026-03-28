"""Per-source masking — secret_field_names hides values in errors."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from dature import Source, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.string import MinLength

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    api_key: Annotated[str, MinLength(value=20)]
    host: str


# --8<-- [start:per-source]
try:
    load(
        Source(
            file=SOURCES_DIR / "masking_per_source.yaml",
            secret_field_names=("api_key",),
        ),
        Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "masking_per_source.yaml")
    assert str(exc) == "Config loading errors (1)"
    assert str(exc.exceptions[0]) == (
        "  [api_key]  Value must have at least 20 characters\n"
        '   ├── api_key: "<REDACTED>"\n'
        "   │             ^^^^^^^^^^\n"
        f"   └── FILE '{source}', line 1"
    )
else:
    raise AssertionError("Expected DatureConfigError")
# --8<-- [end:per-source]
