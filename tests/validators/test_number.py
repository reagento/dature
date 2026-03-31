from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import Source, load
from dature.errors import DatureConfigError
from dature.validators.number import Ge, Gt, Le, Lt


class TestGt:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Gt(0)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 25}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.age == 25

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Gt(18)]

        json_file = tmp_path / "config.json"
        content = '{"age": 18}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [age]  Value must be greater than 18\n"
            f"   ├── {content}\n"
            f"   │           ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestGe:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(18)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 18}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.age == 18

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(18)]

        json_file = tmp_path / "config.json"
        content = '{"age": 17}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [age]  Value must be greater than or equal to 18\n"
            f"   ├── {content}\n"
            f"   │           ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestLt:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Lt(100)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 99}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.age == 99

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Lt(100)]

        json_file = tmp_path / "config.json"
        content = '{"age": 100}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [age]  Value must be less than 100\n"
            f"   ├── {content}\n"
            f"   │           ^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestLe:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Le(100)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 100}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.age == 100

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Le(100)]

        json_file = tmp_path / "config.json"
        content = '{"age": 101}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [age]  Value must be less than or equal to 100\n"
            f"   ├── {content}\n"
            f"   │           ^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestCombined:
    def test_combined_numeric_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(18), Le(65)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 30}')

        metadata = Source(file=json_file)
        result = load(metadata, schema=Config)

        assert result.age == 30

    def test_combined_numeric_validators_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(18), Le(65)]

        json_file = tmp_path / "config.json"
        content = '{"age": 70}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [age]  Value must be less than or equal to 65\n"
            f"   ├── {content}\n"
            f"   │           ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
