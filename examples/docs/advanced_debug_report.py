"""Debug report — get_load_report() to inspect which source provided each field."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, get_load_report, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    workers: int
    tags: list[str]


config = load(
    MergeMetadata(
        sources=(
            LoadMetadata(file_=str(SOURCES_DIR / "defaults.yaml")),
            LoadMetadata(file_=str(SOURCES_DIR / "overrides.yaml")),
        ),
    ),
    Config,
    debug=True,
)

report = get_load_report(config)
if report is not None:
    for origin in report.field_origins:
        print(f"{origin.key} = {origin.value!r}  <-- source {origin.source_index} ({origin.source_file})")
