from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Any

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Ge, Le
from dature.validators.sequence import MinItems, UniqueItems
from dature.validators.string import MaxLength, MinLength, RegexPattern


class TestMultipleFields:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(value=3), MaxLength(value=50)]
            age: Annotated[int, Ge(value=0), Le(value=150)]
            tags: Annotated[list[str], MinItems(value=1), UniqueItems()]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice", "age": 30, "tags": ["python", "coding"]}')

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.name == "Alice"
        assert result.age == 30
        assert result.tags == ["python", "coding"]

    def test_all_invalid(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(value=3), MaxLength(value=50)]
            age: Annotated[int, Ge(value=0), Le(value=150)]
            tags: Annotated[list[str], MinItems(value=1), UniqueItems()]

        json_file = tmp_path / "config.json"
        content = '{"name": "AB", "age": 200, "tags": []}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 3
        assert str(e) == dedent(f"""\
            Config loading errors (3)

              [name]  Value must have at least 3 characters
               └── FILE '{json_file}', line 1
                   {content}

              [age]  Value must be less than or equal to 150
               └── FILE '{json_file}', line 1
                   {content}

              [tags]  Value must have at least 1 items
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestNestedDataclass:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Address:
            city: Annotated[str, MinLength(value=2)]
            zip_code: Annotated[str, RegexPattern(pattern=r"^\d{5}$")]

        @dataclass
        class User:
            name: Annotated[str, MinLength(value=3)]
            age: Annotated[int, Ge(value=18)]
            address: Address

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"name": "Alice", "age": 30, "address": {"city": "NYC", "zip_code": "12345"}}',
        )

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, User)

        assert result.name == "Alice"
        assert result.age == 30
        assert result.address.city == "NYC"
        assert result.address.zip_code == "12345"

    def test_all_invalid(self, tmp_path: Path):
        @dataclass
        class Address:
            city: Annotated[str, MinLength(value=2)]
            zip_code: Annotated[str, RegexPattern(pattern=r"^\d{5}$")]

        @dataclass
        class User:
            name: Annotated[str, MinLength(value=3)]
            age: Annotated[int, Ge(value=18)]
            address: Address

        json_file = tmp_path / "config.json"
        content = '{"name": "Al", "age": 15, "address": {"city": "N", "zip_code": "ABCDE"}}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, User)

        e = exc_info.value
        assert len(e.exceptions) == 4
        assert str(e) == dedent(f"""\
            User loading errors (4)

              [name]  Value must have at least 3 characters
               └── FILE '{json_file}', line 1
                   {content}

              [age]  Value must be greater than or equal to 18
               └── FILE '{json_file}', line 1
                   {content}

              [address.city]  Value must have at least 2 characters
               └── FILE '{json_file}', line 1
                   {content}

              [address.zip_code]  Value must match pattern '^\\d{{5}}$'
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestCustomErrorMessage:
    def test_custom_error_message(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(value=18, error_message="Age must be 18 or older")]

        json_file = tmp_path / "config.json"
        content = '{"age": 15}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [age]  Age must be 18 or older
               └── FILE '{json_file}', line 1
                   {content}
            """)


class TestDictListDict:
    def test_raw_dict_field_validator_success(self, tmp_path: Path):
        @dataclass
        class Config:
            groups: Annotated[dict[str, list[dict[str, Any]]], MinItems(value=1)]

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"groups": {"admins": [{"name": "Alice"}]}}',
        )

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.groups == {"admins": [{"name": "Alice"}]}

    def test_raw_dict_field_validator_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            groups: Annotated[dict[str, list[dict[str, Any]]], MinItems(value=1)]

        json_file = tmp_path / "config.json"
        content = '{"groups": {}}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == dedent(f"""\
            Config loading errors (1)

              [groups]  Value must have at least 1 items
               └── FILE '{json_file}', line 1
                   {content}
            """)

    def test_nested_dataclass_in_dict_list_success(self, tmp_path: Path):
        @dataclass
        class Member:
            name: Annotated[str, MinLength(value=2)]
            role: Annotated[str, MinLength(value=3)]

        @dataclass
        class Config:
            teams: dict[str, list[Member]]

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"teams": {"backend": [{"name": "Alice", "role": "admin"}]}}',
        )

        metadata = LoadMetadata(file_=json_file)
        result = load(metadata, Config)

        assert result.teams["backend"][0].name == "Alice"
        assert result.teams["backend"][0].role == "admin"

    def test_nested_dataclass_in_dict_list_validation_fails(self, tmp_path: Path):
        @dataclass
        class Member:
            name: Annotated[str, MinLength(value=2)]
            role: Annotated[str, MinLength(value=3)]

        @dataclass
        class Config:
            teams: dict[str, list[Member]]

        json_file = tmp_path / "config.json"
        content = '{"teams": {"backend": [{"name": "A", "role": "ab"}]}}'
        json_file.write_text(content)

        metadata = LoadMetadata(file_=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 2
        assert str(e) == dedent(f"""\
            Config loading errors (2)

              [teams.backend.0.name]  Value must have at least 2 characters
               └── FILE '{json_file}', line 1
                   {content}

              [teams.backend.0.role]  Value must have at least 3 characters
               └── FILE '{json_file}', line 1
                   {content}
            """)
