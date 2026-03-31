from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import Source, load
from dature.errors import DatureConfigError
from dature.validators.string import MaxLength, MinLength, RegexPattern


class TestMinLength:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(3)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.name == "Alice"

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(5)]

        json_file = tmp_path / "config.json"
        content = '{"name": "Bob"}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at least 5 characters\n"
            f"   ├── {content}\n"
            f"   │             ^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestMaxLength:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MaxLength(10)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.name == "Alice"

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MaxLength(5)]

        json_file = tmp_path / "config.json"
        content = '{"name": "Alexander"}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at most 5 characters\n"
            f"   ├── {content}\n"
            f"   │             ^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestRegexPattern:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            email: Annotated[str, RegexPattern(r"^[\w\.-]+@[\w\.-]+\.\w+$")]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"email": "test@example.com"}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.email == "test@example.com"

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            email: Annotated[str, RegexPattern(r"^[\w\.-]+@[\w\.-]+\.\w+$")]

        json_file = tmp_path / "config.json"
        content = '{"email": "invalid-email"}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [email]  Value must match pattern '^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$'\n"
            f"   ├── {content}\n"
            f"   │              ^^^^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestCombined:
    def test_combined_string_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            username: Annotated[str, MinLength(3), MaxLength(20)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"username": "john_doe"}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.username == "john_doe"

    def test_combined_string_validators_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            username: Annotated[str, MinLength(3), MaxLength(20)]

        json_file = tmp_path / "config.json"
        content = '{"username": "this_is_a_very_long_username_that_exceeds_limit"}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [username]  Value must have at most 20 characters\n"
            f"   ├── {content}\n"
            f"   │                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
