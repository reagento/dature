"""Root validator — error example."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.root import RootValidator

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


def check_debug_not_on_production(obj: Config) -> bool:
    if obj.host != "localhost" and obj.debug:
        return False
    return True


try:
    load(
        LoadMetadata(
            file_=SOURCES_DIR / "validation_root_invalid.yaml",
            root_validators=(
                RootValidator(
                    func=check_debug_not_on_production,
                    error_message="debug=True is not allowed on non-localhost hosts",
                ),
            ),
        ),
        Config,
    )
except DatureConfigError as exc:
    source = str(SOURCES_DIR / "validation_root_invalid.yaml")
    assert str(exc) == dedent(f"""\
        Config loading errors (1)

          [<root>]  debug=True is not allowed on non-localhost hosts
           └── FILE '{source}'
        """)
