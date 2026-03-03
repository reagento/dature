"""Global configure() — customize masking, error display, loading defaults."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, configure, load
from dature.config import ErrorDisplayConfig, LoadingConfig, MaskingConfig

SOURCES_DIR = Path(__file__).parent / "sources"

configure(
    masking=MaskingConfig(mask_char="X", min_visible_chars=1),
    error_display=ErrorDisplayConfig(max_visible_lines=5),
    loading=LoadingConfig(cache=True, debug=False),
)


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


config = load(LoadMetadata(file_=str(SOURCES_DIR / "app.yaml")), Config)

print(f"host: {config.host}")
print(f"port: {config.port}")

# Reset to defaults
configure(
    masking=MaskingConfig(),
    error_display=ErrorDisplayConfig(),
    loading=LoadingConfig(),
)
