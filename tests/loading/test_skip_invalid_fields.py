"""Tests for skip_if_invalid / skip_invalid_fields feature."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import F, Merge, MergeStrategy, Source, load
from dature.errors.exceptions import DatureConfigError


class TestMergeSkipInvalidFields:
    def test_fallback_to_other_source(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc"}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Merge(
                Source(file_=source1),
                Source(file_=source2),
                skip_invalid_fields=True,
            ),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_all_sources_invalid_with_default(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc"}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"port": "def"}')

        @dataclass
        class Config:
            host: str
            port: int = 9090

        result = load(
            Merge(
                Source(file_=source1),
                Source(file_=source2),
                skip_invalid_fields=True,
            ),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 9090

    def test_all_sources_invalid_no_default_raises(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc"}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"port": "def"}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Merge(
                    Source(file_=source1),
                    Source(file_=source2),
                    skip_invalid_fields=True,
                ),
                Config,
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            f"  [port]  Missing required field (invalid in: json '{source1}', json '{source2}')\n"
            f'   ├── {{"host": "localhost", "port": "abc"}}\n'
            f"   ├── FILE '{source1}', line 1\n"
            f'   ├── {{"port": "def"}}\n'
            f"   └── FILE '{source2}', line 1"
        )

    def test_nested_dataclass(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"db": {"host": "s1-host", "port": "abc"}}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"db": {"host": "s2-host", "port": 5432}}')

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            db: Database

        result = load(
            Merge(
                Source(file_=source1),
                Source(file_=source2),
                skip_invalid_fields=True,
            ),
            Config,
        )

        assert result.db.host == "s2-host"
        assert result.db.port == 5432

    def test_per_source_override(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc"}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Merge(
                Source(file_=source1, skip_if_invalid=True),
                Source(file_=source2),
            ),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_global_flag(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc"}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Merge(
                Source(file_=source1),
                Source(file_=source2),
                skip_invalid_fields=True,
            ),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_backward_compat_no_skip(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc"}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Merge(
                    Source(file_=source1),
                ),
                Config,
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            f"  [port]  invalid literal for int() with base 10: 'abc'\n"
            f'   ├── {{"host": "localhost", "port": "abc"}}\n'
            f"   │                                  ^^^\n"
            f"   └── FILE '{source1}', line 1"
        )

    def test_raise_on_conflict_with_skip(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc"}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"host": "localhost", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Merge(
                Source(file_=source1),
                Source(file_=source2),
                strategy=MergeStrategy.RAISE_ON_CONFLICT,
                skip_invalid_fields=True,
            ),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_skip_specific_fields_only(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc", "timeout": "bad"}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int
            timeout: int = 30

        result = load(
            Merge(
                Source(
                    file_=source1,
                    skip_if_invalid=(F[Config].port, F[Config].timeout),
                ),
                Source(file_=source2),
            ),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 8080
        assert result.timeout == 30

    def test_skip_specific_fields_non_listed_field_raises(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": 123, "port": "abc"}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Merge(
                    Source(
                        file_=source1,
                        skip_if_invalid=(F[Config].port,),
                    ),
                ),
                Config,
            )

        err = exc_info.value
        assert len(err.exceptions) == 2
        assert str(err) == "Config loading errors (2)"
        assert str(err.exceptions[0]) == (
            f"  [host]  Expected str, got int\n"
            f'   ├── {{"host": 123, "port": "abc"}}\n'
            f"   │            ^^^\n"
            f"   └── FILE '{source1}', line 1"
        )
        assert str(err.exceptions[1]) == (
            f"  [port]  Missing required field (invalid in: json '{source1}')\n"
            f'   ├── {{"host": 123, "port": "abc"}}\n'
            f"   └── FILE '{source1}', line 1"
        )

    def test_log_warnings(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"host": "localhost", "port": "abc"}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        with caplog.at_level(logging.WARNING, logger="dature"):
            load(
                Merge(
                    Source(file_=source1),
                    Source(file_=source2),
                    skip_invalid_fields=True,
                ),
                Config,
            )

        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages == [
            "[Config] Source 0: Skipped invalid field 'port'",
            "[Config] Source 1: Skipped invalid field 'host'",
        ]


class TestSingleSourceSkipInvalidFields:
    def test_skip_with_default(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": "abc"}')

        @dataclass
        class Config:
            host: str
            port: int = 8080

        result = load(
            Source(file_=json_file, skip_if_invalid=True),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_skip_without_default_raises(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": "abc"}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file_=json_file, skip_if_invalid=True),
                Config,
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        assert str(err) == "Config loading errors (1)"
        assert str(err.exceptions[0]) == (
            f"  [port]  Missing required field (invalid in: json '{json_file}')\n"
            f'   ├── {{"host": "localhost", "port": "abc"}}\n'
            f"   └── FILE '{json_file}', line 1"
        )

    def test_single_source_decorator_skip(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": "abc"}')

        @load(Source(file_=json_file, skip_if_invalid=True))
        @dataclass
        class Config:
            host: str
            port: int = 8080

        cfg = Config()
        assert cfg.host == "localhost"
        assert cfg.port == 8080

    def test_single_source_specific_fields(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": "abc", "timeout": 60}')

        @dataclass
        class Config:
            host: str
            port: int = 9090
            timeout: int = 30

        result = load(
            Source(
                file_=json_file,
                skip_if_invalid=(F[Config].port,),
            ),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 9090
        assert result.timeout == 60

    def test_single_source_log_warnings(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": "abc"}')

        @dataclass
        class Config:
            host: str
            port: int = 8080

        with caplog.at_level(logging.WARNING, logger="dature"):
            load(
                Source(file_=json_file, skip_if_invalid=True),
                Config,
            )

        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages == ["[Config] Skipped invalid field 'port'"]


class TestSkipInvalidSameFieldNameNested:
    def test_skip_root_field_not_nested(self, tmp_path: Path):
        source = tmp_path / "config.json"
        source.write_text('{"port": "abc", "inner": {"port": 9090}}')

        @dataclass
        class Inner:
            port: int

        @dataclass
        class Config:
            port: int = 3000
            inner: Inner = None  # type: ignore[assignment]

        result = load(
            Source(
                file_=source,
                skip_if_invalid=(F[Config].port,),
            ),
            Config,
        )

        assert result.port == 3000
        assert result.inner.port == 9090

    def test_skip_nested_field_not_root(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"port": 8080, "inner": {"port": "abc"}}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"inner": {"port": 9090}}')

        @dataclass
        class Inner:
            port: int

        @dataclass
        class Config:
            port: int
            inner: Inner

        result = load(
            Merge(
                Source(
                    file_=source1,
                    skip_if_invalid=(F[Config].inner.port,),
                ),
                Source(file_=source2),
            ),
            Config,
        )

        assert result.port == 8080
        assert result.inner.port == 9090

    def test_skip_both_root_and_nested(self, tmp_path: Path):
        source1 = tmp_path / "s1.json"
        source1.write_text('{"port": "abc", "inner": {"port": "def"}}')

        source2 = tmp_path / "s2.json"
        source2.write_text('{"port": 8080, "inner": {"port": 9090}}')

        @dataclass
        class Inner:
            port: int

        @dataclass
        class Config:
            port: int
            inner: Inner

        result = load(
            Merge(
                Source(
                    file_=source1,
                    skip_if_invalid=(F[Config].port, F[Config].inner.port),
                ),
                Source(file_=source2),
            ),
            Config,
        )

        assert result.port == 8080
        assert result.inner.port == 9090
