"""Report on error — get_load_report() from the dataclass type after a failed load."""

from dataclasses import dataclass
from pathlib import Path

from dature import LoadMetadata, MergeMetadata, get_load_report, load
from dature.errors.exceptions import DatureConfigError

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    workers: int
    tags: list[str]


try:
    config = load(
        MergeMetadata(
            sources=(
                LoadMetadata(file_=SOURCES_DIR / "overrides.yaml"),
                LoadMetadata(file_=SOURCES_DIR / "invalid_defaults.yaml"),
            ),
        ),
        Config,
        debug=True,
    )
except DatureConfigError:
    report = get_load_report(Config)
    if report is not None:
        print(f"dataclass_name: {report.dataclass_name}")
        print(f"strategy: {report.strategy}")
        print(f"merged_data: {report.merged_data}")
        print()
        for src in report.sources:
            print(f"source {src.index}: loader={src.loader_type}, file={src.file_path}")
            print(f"  raw_data: {src.raw_data}")
        print()
        for origin in report.field_origins:
            print(
                f"{origin.key} = {origin.value!r}  <-- source {origin.source_index} ({origin.source_file})",
            )

# Output:
# dataclass_name: Config
# strategy: last_wins
# merged_data: {'host': 'localhost', 'port': 'not_a_number', 'debug': False, 'workers': 1, 'tags': ['default']}
#
# source 0: loader=yaml1.2, file=.../overrides.yaml
#   raw_data: {'host': 'production.example.com', 'port': 8080, 'debug': True, 'workers': 4, 'tags': ['web', 'api']}
# source 1: loader=yaml1.2, file=.../invalid_defaults.yaml
#   raw_data: {'host': 'localhost', 'port': 'not_a_number', 'debug': False, 'workers': 1, 'tags': ['default']}
#
# debug = False  <-- source 1 (.../invalid_defaults.yaml)
# host = 'localhost'  <-- source 1 (.../invalid_defaults.yaml)
# port = 'not_a_number'  <-- source 1 (.../invalid_defaults.yaml)
# tags = ['default']  <-- source 1 (.../invalid_defaults.yaml)
# workers = 1  <-- source 1 (.../invalid_defaults.yaml)
