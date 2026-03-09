from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Annotated

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError


@dataclass(frozen=True, slots=True, kw_only=True)
class Divisible:
    value: int
    error_message: str = "Value must be divisible by {value}"

    def get_validator_func(self) -> Callable[[int], bool]:
        def validate(val: int) -> bool:
            return val % self.value == 0

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(value=self.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class StartsWith:
    prefix: str
    error_message: str = "Value must start with '{prefix}'"

    def get_validator_func(self) -> Callable[[str], bool]:
        def validate(val: str) -> bool:
            return val.startswith(self.prefix)

        return validate

    def get_error_message(self) -> str:
        return self.error_message.format(prefix=self.prefix)


class TestCustomFieldValidator:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, Divisible(value=5)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"count": 10}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.count == 10

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, Divisible(value=5)]

        json_file = tmp_path / "config.json"
        content = '{"count": 7}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [count]  Value must be divisible by 5
               └── FILE '{json_file}', line 1
                   {content}
            """)

    def test_custom_error_message(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, Divisible(value=3, error_message="Must be a multiple of {value}")]

        json_file = tmp_path / "config.json"
        content = '{"count": 7}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [count]  Must be a multiple of 3
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestCustomStringValidator:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            url: Annotated[str, StartsWith(prefix="https://")]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"url": "https://example.com"}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.url == "https://example.com"

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            url: Annotated[str, StartsWith(prefix="https://")]

        json_file = tmp_path / "config.json"
        content = '{"url": "http://example.com"}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [url]  Value must start with 'https://'
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestCustomValidatorWithDecorator:
    def test_success(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080}')

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            port: Annotated[int, Divisible(value=10)]

        config = Config()
        assert config.port == 8080

    def test_failure(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        content = '{"port": 8081}'
        json_file.write_text(content)

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            port: Annotated[int, Divisible(value=10)]

        with pytest.raises(DatureConfigError) as exc_info:
            Config()

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [port]  Value must be divisible by 10
               └── FILE '{json_file}', line 1
                   {content}
            """)

    def test_direct_instantiation_validates(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        content = '{"port": 8080}'
        json_file.write_text(content)

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            port: Annotated[int, Divisible(value=10)]

        with pytest.raises(DatureConfigError) as exc_info:
            Config(port=8081)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [port]  Value must be divisible by 10
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestMultipleCustomValidators:
    def test_combined_success(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, Divisible(value=5)]
            url: Annotated[str, StartsWith(prefix="https://")]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"count": 15, "url": "https://example.com"}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.count == 15
        assert result.url == "https://example.com"

    def test_all_fail(self, tmp_path: Path):
        @dataclass
        class Config:
            count: Annotated[int, Divisible(value=5)]
            url: Annotated[str, StartsWith(prefix="https://")]

        json_file = tmp_path / "config.json"
        content = '{"count": 7, "url": "http://example.com"}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 2
        assert str(e) == dedent(f"""\
            Config loading errors (2)

              [count]  Value must be divisible by 5
               └── FILE '{json_file}', line 1
                   {content}

              [url]  Value must start with 'https://'
               └── FILE '{json_file}', line 1
                   {content}
            """)
