"""Report on error — dature.get_load_report() from the dataclass type after a failed load."""

from dataclasses import dataclass
from pathlib import Path

import dature
from dature.errors.exceptions import DatureConfigError

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


try:
    config = dature.load(
        dature.Source(file=SHARED_DIR / "common_overrides.yaml"),
        dature.Source(file=SOURCES_DIR / "advanced_debug_error_defaults.yaml"),
        dataclass_=Config,
        debug=True,
    )
except DatureConfigError:
    report = dature.get_load_report(Config)
    assert report is not None

    assert report.dataclass_name == "Config"
    assert report.strategy == "last_wins"
    assert report.merged_data == {
        "host": "localhost",
        "port": "not_a_number",
        "tags": ["default"],
    }

    assert len(report.sources) == 2

    assert report.sources[0].index == 0
    assert report.sources[0].loader_type == "yaml1.2"
    assert "overrides" in str(report.sources[0].file_path)
    assert report.sources[0].raw_data == {
        "host": "production.example.com",
        "port": 8080,
        "tags": ["web", "api"],
    }

    assert report.sources[1].index == 1
    assert report.sources[1].loader_type == "yaml1.2"
    assert "advanced_debug_error_defaults" in str(report.sources[1].file_path)
    assert report.sources[1].raw_data == {
        "host": "localhost",
        "port": "not_a_number",
        "tags": ["default"],
    }

    assert len(report.field_origins) == 3
    for origin in report.field_origins:
        assert origin.source_index == 1
        assert "advanced_debug_error_defaults" in str(origin.source_file)
