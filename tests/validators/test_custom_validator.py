"""Tests for V.check — escape-hatch for arbitrary user predicates.

Previously, users defined custom dataclass validators with ``get_validator_func``
and ``get_error_message`` methods. After the V DSL refactor that pattern is
no longer supported — ``V.check(func, error_message=...)`` is the sanctioned way
to express validation logic not covered by built-in predicates.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import JsonSource, V, load
from dature.errors import DatureConfigError


class TestVCheckAnnotated:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, V.check(lambda v: v % 5 == 0, error_message="Value must be divisible by 5")]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"count": 10}')

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=Config)

        assert result.count == 10

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, V.check(lambda v: v % 5 == 0, error_message="Value must be divisible by 5")]

        json_file = tmp_path / "config.json"
        content = '{"count": 7}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [count]  Value must be divisible by 5\n"
            f"   ├── {content}\n"
            f"   │             ^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_custom_error_message(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, V.check(lambda v: v % 3 == 0, error_message="Must be a multiple of 3")]

        json_file = tmp_path / "config.json"
        content = '{"count": 7}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [count]  Must be a multiple of 3\n"
            f"   ├── {content}\n"
            f"   │             ^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestVCheckOnStrings:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            url: Annotated[
                str,
                V.check(lambda v: v.startswith("https://"), error_message="Value must start with 'https://'"),
            ]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"url": "https://example.com"}')

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=Config)

        assert result.url == "https://example.com"

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            url: Annotated[
                str,
                V.check(lambda v: v.startswith("https://"), error_message="Value must start with 'https://'"),
            ]

        json_file = tmp_path / "config.json"
        content = '{"url": "http://example.com"}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [url]  Value must start with 'https://'\n"
            f"   ├── {content}\n"
            f"   │            ^^^^^^^^^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestVCheckWithDecorator:
    def test_success(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080}')

        @load(JsonSource(file=json_file))
        @dataclass
        class Config:
            port: Annotated[int, V.check(lambda v: v % 10 == 0, error_message="Value must be divisible by 10")]

        config = Config()
        assert config.port == 8080

    def test_failure(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        content = '{"port": 8081}'
        json_file.write_text(content)

        @load(JsonSource(file=json_file))
        @dataclass
        class Config:
            port: Annotated[int, V.check(lambda v: v % 10 == 0, error_message="Value must be divisible by 10")]

        with pytest.raises(DatureConfigError) as exc_info:
            Config()

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [port]  Value must be divisible by 10\n"
            f"   ├── {content}\n"
            f"   │            ^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_direct_instantiation_validates(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        content = '{"port": 8080}'
        json_file.write_text(content)

        @load(JsonSource(file=json_file))
        @dataclass
        class Config:
            port: Annotated[int, V.check(lambda v: v % 10 == 0, error_message="Value must be divisible by 10")]

        with pytest.raises(DatureConfigError) as exc_info:
            Config(port=8081)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [port]  Value must be divisible by 10\n   ├── {content}\n   └── FILE '{json_file}', line 1"
        )


class TestMultipleVCheckPredicates:
    def test_combined_success(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, V.check(lambda v: v % 5 == 0, error_message="Value must be divisible by 5")]
            url: Annotated[
                str,
                V.check(lambda v: v.startswith("https://"), error_message="Value must start with 'https://'"),
            ]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"count": 15, "url": "https://example.com"}')

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=Config)

        assert result.count == 15
        assert result.url == "https://example.com"

    def test_all_fail(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, V.check(lambda v: v % 5 == 0, error_message="Value must be divisible by 5")]
            url: Annotated[
                str,
                V.check(lambda v: v.startswith("https://"), error_message="Value must start with 'https://'"),
            ]

        json_file = tmp_path / "config.json"
        content = '{"count": 7, "url": "http://example.com"}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 2
        assert str(e) == "Config loading errors (2)"
        assert str(e.exceptions[0]) == (
            f"  [count]  Value must be divisible by 5\n"
            f"   ├── {content}\n"
            f"   │             ^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[1]) == (
            f"  [url]  Value must start with 'https://'\n"
            f"   ├── {content}\n"
            f"   │                        ^^^^^^^^^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
