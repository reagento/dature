"""Root validator — validate the entire object after loading."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load
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


config = load(
    LoadMetadata(
        file_=str(SOURCES_DIR / "app.yaml"),
        root_validators=(
            RootValidator(
                func=check_debug_not_on_production,
                error_message="debug=True is not allowed on non-localhost hosts",
            ),
        ),
    ),
    Config,
)

print(f"host: {config.host}")
print(f"port: {config.port}")
print(f"debug: {config.debug}")
