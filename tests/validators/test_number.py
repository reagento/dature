from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Annotated

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Ge, Gt, Le, Lt


class TestGt:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Gt(value=0)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 25}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.age == 25

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Gt(value=18)]

        json_file = tmp_path / "config.json"
        content = '{"age": 18}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [age]  Value must be greater than 18
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestGe:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(value=18)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 18}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.age == 18

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(value=18)]

        json_file = tmp_path / "config.json"
        content = '{"age": 17}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [age]  Value must be greater than or equal to 18
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestLt:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Lt(value=100)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 99}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.age == 99

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Lt(value=100)]

        json_file = tmp_path / "config.json"
        content = '{"age": 100}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [age]  Value must be less than 100
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestLe:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Le(value=100)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 100}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.age == 100

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Le(value=100)]

        json_file = tmp_path / "config.json"
        content = '{"age": 101}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [age]  Value must be less than or equal to 100
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestCombined:
    def test_combined_numeric_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(value=18), Le(value=65)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"age": 30}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.age == 30

    def test_combined_numeric_validators_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(value=18), Le(value=65)]

        json_file = tmp_path / "config.json"
        content = '{"age": 70}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [age]  Value must be less than or equal to 65
               └── FILE '{json_file}', line 1
                   {content}
            """)
