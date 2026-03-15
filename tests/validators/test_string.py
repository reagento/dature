from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.string import MaxLength, MinLength, RegexPattern


class TestMinLength:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(value=3)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.name == "Alice"

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(value=5)]

        json_file = tmp_path / "config.json"
        content = '{"name": "Bob"}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at least 5 characters\n   └── FILE '{json_file}', line 1\n       {content}"
        )


class TestMaxLength:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MaxLength(value=10)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.name == "Alice"

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MaxLength(value=5)]

        json_file = tmp_path / "config.json"
        content = '{"name": "Alexander"}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at most 5 characters\n   └── FILE '{json_file}', line 1\n       {content}"
        )


class TestRegexPattern:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            email: Annotated[str, RegexPattern(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"email": "test@example.com"}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.email == "test@example.com"

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            email: Annotated[str, RegexPattern(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

        json_file = tmp_path / "config.json"
        content = '{"email": "invalid-email"}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [email]  Value must match pattern '^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$'\n"
            f"   └── FILE '{json_file}', line 1\n"
            f"       {content}"
        )


class TestCombined:
    def test_combined_string_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            username: Annotated[str, MinLength(value=3), MaxLength(value=20)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"username": "john_doe"}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.username == "john_doe"

    def test_combined_string_validators_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            username: Annotated[str, MinLength(value=3), MaxLength(value=20)]

        json_file = tmp_path / "config.json"
        content = '{"username": "this_is_a_very_long_username_that_exceeds_limit"}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [username]  Value must have at most 20 characters\n   └── FILE '{json_file}', line 1\n       {content}"
        )
