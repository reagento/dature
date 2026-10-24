from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass

import dature
from dature.errors import DatureConfigError
from dature.strategies.source import SourceLastWins


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


try:
    config = dature.load(
        dature.Yaml12Source(file=SHARED_DIR / "common_overrides.yaml"),
        dature.Yaml12Source(
            file=SOURCES_DIR / "advanced_debug_error_defaults.yaml",
        ),
        schema=Config,
        field_merges={dature.F[Config].tags: "append"},
        debug=True,
    )
except DatureConfigError:
    report = dature.load_report(Config)
    assert report is not None

    assert report.dataclass_name == "Config"
    assert isinstance(report.strategy, SourceLastWins)

    assert report.merged_data == {
        "host": "<REDACTED>",
        "port": "<REDACTED>",
        "tags": ["<REDACTED>", "<REDACTED>", "<REDACTED>"],
    }

    assert len(report.sources) == 2

    assert report.sources[0].index == 0
    assert report.sources[0].loader_type == "yaml1.2"
    assert report.sources[0].file_path == str(
        SHARED_DIR / "common_overrides.yaml"
    )
    assert report.sources[0].raw_data == {
        "host": "<REDACTED>",
        "port": "<REDACTED>",
        "tags": ["<REDACTED>", "<REDACTED>"],
    }

    assert report.sources[1].index == 1
    assert report.sources[1].loader_type == "yaml1.2"
    assert report.sources[1].file_path == str(
        SOURCES_DIR / "advanced_debug_error_defaults.yaml"
    )
    assert report.sources[1].raw_data == {
        "host": "<REDACTED>",
        "port": "<REDACTED>",
        "tags": ["<REDACTED>"],
    }

    assert len(report.field_origins) == 3
    host, port, tags = report.field_origins

    for origin in (host, port):
        assert len(origin.sources) == 1
        assert origin.sources[0].source_index == 1
        assert origin.sources[0].source_file == str(
            SOURCES_DIR / "advanced_debug_error_defaults.yaml"
        )

    assert tags.key == "tags"
    assert [s.source_index for s in tags.sources] == [0, 1]
# --8<-- [end:example]
