"""__post_init__ validation — error example."""

from dataclasses import dataclass
from pathlib import Path

import dature

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


dature.load(dature.Source(file=SOURCES_DIR / "validation_post_init_invalid.yaml"), schema=Config)
