"""__post_init__ validation — cross-field checks via standard dataclass."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False

    def __post_init__(self) -> None:
        if self.port < 1 or self.port > 65535:
            msg = f"port must be between 1 and 65535, got {self.port}"
            raise ValueError(msg)

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


config = load(LoadMetadata(file_=str(SOURCES_DIR / "app.yaml")), Config)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 8080
print(f"address: {config.address}")  # address: localhost:8080
