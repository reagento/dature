"""Tests for LoadReport and debug logging."""

import logging
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import Merge, MergeStrategy, Source, get_load_report, load
from dature.errors.exceptions import DatureConfigError
from dature.load_report import FieldOrigin, LoadReport, SourceEntry
from dature.validators.number import Ge


class TestGetLoadReportMergeFunction:
    def test_last_wins(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Merge(
                Source(file=defaults),
                Source(file=overrides),
            ),
            Config,
            debug=True,
        )

        report = get_load_report(result)

        expected = LoadReport(
            dataclass_name="Config",
            strategy=MergeStrategy.LAST_WINS,
            sources=(
                SourceEntry(
                    index=0,
                    file_path=str(defaults),
                    loader_type="json",
                    raw_data={"host": "localhost", "port": 3000},
                ),
                SourceEntry(
                    index=1,
                    file_path=str(overrides),
                    loader_type="json",
                    raw_data={"port": 8080},
                ),
            ),
            field_origins=(
                FieldOrigin(
                    key="host",
                    value="localhost",
                    source_index=0,
                    source_file=str(defaults),
                    source_loader_type="json",
                ),
                FieldOrigin(
                    key="port",
                    value=8080,
                    source_index=1,
                    source_file=str(overrides),
                    source_loader_type="json",
                ),
            ),
            merged_data={"host": "localhost", "port": 8080},
        )
        assert expected == report

    def test_first_wins(self, tmp_path: Path):
        first = tmp_path / "first.json"
        first.write_text('{"host": "first-host", "port": 1000}')

        second = tmp_path / "second.json"
        second.write_text('{"host": "second-host", "port": 2000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Merge(
                Source(file=first),
                Source(file=second),
                strategy=MergeStrategy.FIRST_WINS,
            ),
            Config,
            debug=True,
        )

        report = get_load_report(result)

        expected = LoadReport(
            dataclass_name="Config",
            strategy=MergeStrategy.FIRST_WINS,
            sources=(
                SourceEntry(
                    index=0,
                    file_path=str(first),
                    loader_type="json",
                    raw_data={"host": "first-host", "port": 1000},
                ),
                SourceEntry(
                    index=1,
                    file_path=str(second),
                    loader_type="json",
                    raw_data={"host": "second-host", "port": 2000},
                ),
            ),
            field_origins=(
                FieldOrigin(
                    key="host",
                    value="second-host",
                    source_index=0,
                    source_file=str(first),
                    source_loader_type="json",
                ),
                FieldOrigin(
                    key="port",
                    value=2000,
                    source_index=0,
                    source_file=str(first),
                    source_loader_type="json",
                ),
            ),
            merged_data={"host": "first-host", "port": 1000},
        )
        assert expected == report

    def test_nested_field_origins(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"database": {"host": "localhost", "port": 5432}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"database": {"host": "prod-host"}}')

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database

        result = load(
            Merge(
                Source(file=defaults),
                Source(file=overrides),
            ),
            Config,
            debug=True,
        )

        report = get_load_report(result)
        assert report is not None

        expected_origins = (
            FieldOrigin(
                key="database.host",
                value="prod-host",
                source_index=1,
                source_file=str(overrides),
                source_loader_type="json",
            ),
            FieldOrigin(
                key="database.port",
                value=5432,
                source_index=0,
                source_file=str(defaults),
                source_loader_type="json",
            ),
        )
        assert expected_origins == report.field_origins


class TestGetLoadReportSingleSource:
    def test_single_source_function(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        result = load(Source(file=json_file), Config, debug=True)

        report = get_load_report(result)

        expected = LoadReport(
            dataclass_name="Config",
            strategy=None,
            sources=(
                SourceEntry(
                    index=0,
                    file_path=str(json_file),
                    loader_type="json",
                    raw_data={"name": "test", "port": 8080},
                ),
            ),
            field_origins=(
                FieldOrigin(
                    key="name",
                    value="test",
                    source_index=0,
                    source_file=str(json_file),
                    source_loader_type="json",
                ),
                FieldOrigin(
                    key="port",
                    value=8080,
                    source_index=0,
                    source_file=str(json_file),
                    source_loader_type="json",
                ),
            ),
            merged_data={"name": "test", "port": 8080},
        )
        assert expected == report


class TestGetLoadReportDecorator:
    def test_merge_decorator(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 9090}')

        meta = Merge(
            Source(file=defaults),
            Source(file=overrides),
        )

        @load(meta, debug=True)
        @dataclass
        class Config:
            host: str
            port: int

        config = Config()
        report = get_load_report(config)
        assert report is not None
        assert report.strategy == MergeStrategy.LAST_WINS
        assert len(report.sources) == 2

    def test_single_source_decorator(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": 3000}')

        @load(Source(file=json_file), debug=True)
        @dataclass
        class Config:
            host: str
            port: int

        config = Config()
        report = get_load_report(config)
        assert report is not None
        assert report.strategy is None
        assert len(report.sources) == 1


class TestGetLoadReportWithoutDebug:
    def test_returns_none_with_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = get_load_report("hello")

        assert result is None
        assert len(w) == 1
        assert str(w[0].message) == "To get LoadReport, pass debug=True to load()"

    def test_no_report_without_debug(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": 3000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(Source(file=json_file), Config)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            report = get_load_report(result)

        assert report is None
        assert len(w) == 1
        assert str(w[0].message) == "To get LoadReport, pass debug=True to load()"


class TestDebugLogging:
    def test_merge_debug_logs(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        with caplog.at_level(logging.DEBUG, logger="dature"):
            load(
                Merge(
                    Source(file=defaults),
                    Source(file=overrides),
                ),
                Config,
            )

        messages = [r.message for r in caplog.records if r.name == "dature"]

        expected = [
            f"[JsonLoader] load_raw: path={defaults},"
            " raw_keys=['host', 'port'], after_preprocessing_keys=['host', 'port']",
            f"[Config] Source 0 loaded: loader=json, file={defaults}, keys=['host', 'port']",
            "[Config] Source 0 raw data: {'host': 'localhost', 'port': 3000}",
            f"[JsonLoader] load_raw: path={overrides}, raw_keys=['port'], after_preprocessing_keys=['port']",
            f"[Config] Source 1 loaded: loader=json, file={overrides}, keys=['port']",
            "[Config] Source 1 raw data: {'port': 8080}",
            "[Config] Merge step 0 (strategy=last_wins): added=['host', 'port'], overwritten=[]",
            "[Config] State after step 0: {'host': 'localhost', 'port': 3000}",
            "[Config] Merge step 1 (strategy=last_wins): added=[], overwritten=['port']",
            "[Config] State after step 1: {'host': 'localhost', 'port': 8080}",
            "[Config] Merged result (strategy=last_wins, 2 sources): {'host': 'localhost', 'port': 8080}",
            f"[Config] Field 'host' = 'localhost'  <-- source 0 ({defaults})",
            f"[Config] Field 'port' = 8080  <-- source 1 ({overrides})",
        ]
        assert expected == messages

    def test_single_source_debug_logs(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": 3000}')

        @dataclass
        class Config:
            host: str
            port: int

        with caplog.at_level(logging.DEBUG, logger="dature"):
            load(Source(file=json_file), Config)

        messages = [r.message for r in caplog.records if r.name == "dature"]

        expected = [
            f"[JsonLoader] load_raw: path={json_file},"
            " raw_keys=['host', 'port'], after_preprocessing_keys=['host', 'port']",
            f"[Config] Single-source load: loader=json, file={json_file}",
            "[Config] Loaded data: {'host': 'localhost', 'port': 3000}",
        ]
        assert expected == messages


class TestLoadReportOnError:
    def test_merge_missing_field(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "localhost"}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "override"}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError):
            load(
                Merge(
                    Source(file=a),
                    Source(file=b),
                ),
                Config,
                debug=True,
            )

        expected = LoadReport(
            dataclass_name="Config",
            strategy=MergeStrategy.LAST_WINS,
            sources=(
                SourceEntry(index=0, file_path=str(a), loader_type="json", raw_data={"host": "localhost"}),
                SourceEntry(index=1, file_path=str(b), loader_type="json", raw_data={"host": "override"}),
            ),
            field_origins=(
                FieldOrigin(
                    key="host",
                    value="override",
                    source_index=1,
                    source_file=str(b),
                    source_loader_type="json",
                ),
            ),
            merged_data={"host": "override"},
        )
        assert expected == get_load_report(Config)

    def test_merge_validation_error(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"port": -5}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "localhost"}')

        @dataclass
        class Config:
            host: str
            port: Annotated[int, Ge(value=0)]

        with pytest.raises(DatureConfigError):
            load(
                Merge(
                    Source(file=a),
                    Source(file=b),
                ),
                Config,
                debug=True,
            )

        expected = LoadReport(
            dataclass_name="Config",
            strategy=MergeStrategy.LAST_WINS,
            sources=(
                SourceEntry(index=0, file_path=str(a), loader_type="json", raw_data={"port": -5}),
                SourceEntry(index=1, file_path=str(b), loader_type="json", raw_data={"host": "localhost"}),
            ),
            field_origins=(
                FieldOrigin(
                    key="host",
                    value="localhost",
                    source_index=1,
                    source_file=str(b),
                    source_loader_type="json",
                ),
                FieldOrigin(key="port", value=-5, source_index=0, source_file=str(a), source_loader_type="json"),
            ),
            merged_data={"host": "localhost", "port": -5},
        )
        assert expected == get_load_report(Config)

    def test_single_source_missing_field(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost"}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError):
            load(Source(file=json_file), Config, debug=True)

        expected = LoadReport(
            dataclass_name="Config",
            strategy=None,
            sources=(
                SourceEntry(index=0, file_path=str(json_file), loader_type="json", raw_data={"host": "localhost"}),
            ),
            field_origins=(
                FieldOrigin(
                    key="host",
                    value="localhost",
                    source_index=0,
                    source_file=str(json_file),
                    source_loader_type="json",
                ),
            ),
            merged_data={"host": "localhost"},
        )
        assert expected == get_load_report(Config)

    def test_single_source_validation_error(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": -1}')

        @dataclass
        class Config:
            port: Annotated[int, Ge(value=0)]

        with pytest.raises(DatureConfigError):
            load(Source(file=json_file), Config, debug=True)

        expected = LoadReport(
            dataclass_name="Config",
            strategy=None,
            sources=(SourceEntry(index=0, file_path=str(json_file), loader_type="json", raw_data={"port": -1}),),
            field_origins=(
                FieldOrigin(
                    key="port",
                    value=-1,
                    source_index=0,
                    source_file=str(json_file),
                    source_loader_type="json",
                ),
            ),
            merged_data={"port": -1},
        )
        assert expected == get_load_report(Config)
