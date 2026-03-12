"""Debug report — get_load_report() to inspect which source provided each field."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, get_load_report, load

SHARED_DIR = Path(__file__).parents[2] / "shared"


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
            LoadMetadata(file_=SHARED_DIR / "common_defaults.yaml"),
            LoadMetadata(file_=SHARED_DIR / "common_overrides.yaml"),
        ),
    ),
    Config,
    debug=True,
)

report = get_load_report(config)
if report is not None:
    for origin in report.field_origins:
        print(
            f"{origin.key} = {origin.value!r}  <-- source {origin.source_index} ({origin.source_file})",
        )

# Output:
# debug = True  <-- source 1 (.../overrides.yaml)
# host = 'production.example.com'  <-- source 1 (.../overrides.yaml)
# port = 8080  <-- source 1 (.../overrides.yaml)
# tags = ['web', 'api']  <-- source 1 (.../overrides.yaml)
# workers = 4  <-- source 1 (.../overrides.yaml)
