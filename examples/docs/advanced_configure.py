"""Global configure() — customize masking, error display, loading defaults."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, configure, get_load_report, load
from dature.config import LoadingConfig

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# 1. Default config — debug is off, no report
config = load(LoadMetadata(file_=str(SOURCES_DIR / "app.yaml")), Config)
report = get_load_report(config)
print(f"has report: {report is not None}")  # has report: False

# 2. Enable debug globally via configure()
configure(loading=LoadingConfig(debug=True))

config = load(LoadMetadata(file_=str(SOURCES_DIR / "app.yaml")), Config)
report = get_load_report(config)
print(f"has report: {report is not None}")  # has report: True

# 3. Reset to defaults — debug is off again
configure(loading=LoadingConfig())

config = load(LoadMetadata(file_=str(SOURCES_DIR / "app.yaml")), Config)
report = get_load_report(config)
print(f"has report: {report is not None}")  # has report: False
