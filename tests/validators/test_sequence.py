from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Annotated

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.sequence import MaxItems, MinItems, UniqueItems


class TestMinItems:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], MinItems(value=2)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": ["python", "typing"]}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.tags == ["python", "typing"]

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], MinItems(value=3)]

        json_file = tmp_path / "config.json"
        content = '{"tags": ["python"]}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [tags]  Value must have at least 3 items
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestMaxItems:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], MaxItems(value=5)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": ["python", "typing"]}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.tags == ["python", "typing"]

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], MaxItems(value=2)]

        json_file = tmp_path / "config.json"
        content = '{"tags": ["python", "typing", "validation"]}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [tags]  Value must have at most 2 items
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestUniqueItems:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], UniqueItems()]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": ["python", "typing", "validation"]}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.tags == ["python", "typing", "validation"]

    def test_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], UniqueItems()]

        json_file = tmp_path / "config.json"
        content = '{"tags": ["python", "typing", "python"]}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [tags]  Value must contain unique items
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestCombined:
    def test_combined_list_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], MinItems(value=2), MaxItems(value=5), UniqueItems()]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": ["python", "typing", "validation"]}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.tags == ["python", "typing", "validation"]

    def test_combined_list_validators_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], MinItems(value=2), MaxItems(value=5), UniqueItems()]

        json_file = tmp_path / "config.json"
        content = '{"tags": ["python", "typing", "validation", "testing", "coding", "extra"]}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [tags]  Value must have at most 5 items
               └── FILE '{json_file}', line 1
                   {content}
            """)
