from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import pytest

from dature import Source, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.number import Ge, Le
from dature.validators.sequence import MinItems, UniqueItems
from dature.validators.string import MaxLength, MinLength, RegexPattern


class TestMultipleFields:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(3), MaxLength(50)]
            age: Annotated[int, Ge(0), Le(150)]
            tags: Annotated[list[str], MinItems(1), UniqueItems()]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice", "age": 30, "tags": ["python", "coding"]}')

        metadata = Source(file=json_file)
        result = load(metadata, dataclass_=Config)

        assert result.name == "Alice"
        assert result.age == 30
        assert result.tags == ["python", "coding"]

    def test_all_invalid(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(3), MaxLength(50)]
            age: Annotated[int, Ge(0), Le(150)]
            tags: Annotated[list[str], MinItems(1), UniqueItems()]

        json_file = tmp_path / "config.json"
        content = '{"name": "AB", "age": 200, "tags": []}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 3
        assert str(e) == "Config loading errors (3)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at least 3 characters\n"
            f"   ├── {content}\n"
            f"   │             ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[1]) == (
            f"  [age]  Value must be less than or equal to 150\n"
            f"   ├── {content}\n"
            f"   │                         ^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[2]) == (
            f"  [tags]  Value must have at least 1 items\n"
            f"   ├── {content}\n"
            f"   │                                      ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestNestedDataclass:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Address:
            city: Annotated[str, MinLength(2)]
            zip_code: Annotated[str, RegexPattern(r"^\d{5}$")]

        @dataclass
        class User:
            name: Annotated[str, MinLength(3)]
            age: Annotated[int, Ge(18)]
            address: Address

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"name": "Alice", "age": 30, "address": {"city": "NYC", "zip_code": "12345"}}',
        )

        metadata = Source(file=json_file)
        result = load(metadata, dataclass_=User)

        assert result.name == "Alice"
        assert result.age == 30
        assert result.address.city == "NYC"
        assert result.address.zip_code == "12345"

    def test_all_invalid(self, tmp_path: Path):
        @dataclass
        class Address:
            city: Annotated[str, MinLength(2)]
            zip_code: Annotated[str, RegexPattern(r"^\d{5}$")]

        @dataclass
        class User:
            name: Annotated[str, MinLength(3)]
            age: Annotated[int, Ge(18)]
            address: Address

        json_file = tmp_path / "config.json"
        content = '{"name": "Al", "age": 15, "address": {"city": "N", "zip_code": "ABCDE"}}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=User)

        e = exc_info.value
        assert len(e.exceptions) == 4
        assert str(e) == "User loading errors (4)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at least 3 characters\n"
            f"   ├── {content}\n"
            f"   │             ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[1]) == (
            f"  [age]  Value must be greater than or equal to 18\n"
            f"   ├── {content}\n"
            f"   │                         ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[2]) == (
            "  [address.city]  Value must have at least 2 characters\n"
            f"   ├── {content}\n"
            f"   │                                                  ^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[3]) == (
            "  [address.zip_code]  Value must match pattern '^\\d{5}$'\n"
            f"   ├── {content}\n"
            f"   │                                                                   ^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestCustomErrorMessage:
    def test_custom_error_message(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, Ge(18, error_message="Age must be 18 or older")]

        json_file = tmp_path / "config.json"
        content = '{"age": 15}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [age]  Age must be 18 or older\n   ├── {content}\n   │           ^^\n   └── FILE '{json_file}', line 1"
        )


class TestDictListDict:
    def test_raw_dict_field_validator_success(self, tmp_path: Path):
        @dataclass
        class Config:
            groups: Annotated[dict[str, list[dict[str, Any]]], MinItems(1)]

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"groups": {"admins": [{"name": "Alice"}]}}',
        )

        metadata = Source(file=json_file)
        result = load(metadata, dataclass_=Config)

        assert result.groups == {"admins": [{"name": "Alice"}]}

    def test_raw_dict_field_validator_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            groups: Annotated[dict[str, list[dict[str, Any]]], MinItems(1)]

        json_file = tmp_path / "config.json"
        content = '{"groups": {}}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [groups]  Value must have at least 1 items\n"
            f"   ├── {content}\n"
            f"   │              ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_nested_dataclass_in_dict_list_success(self, tmp_path: Path):
        @dataclass
        class Member:
            name: Annotated[str, MinLength(2)]
            role: Annotated[str, MinLength(3)]

        @dataclass
        class Config:
            teams: dict[str, list[Member]]

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"teams": {"backend": [{"name": "Alice", "role": "admin"}]}}',
        )

        metadata = Source(file=json_file)
        result = load(metadata, dataclass_=Config)

        assert result.teams["backend"][0].name == "Alice"
        assert result.teams["backend"][0].role == "admin"

    def test_nested_dataclass_in_dict_list_validation_fails(self, tmp_path: Path):
        @dataclass
        class Member:
            name: Annotated[str, MinLength(2)]
            role: Annotated[str, MinLength(3)]

        @dataclass
        class Config:
            teams: dict[str, list[Member]]

        json_file = tmp_path / "config.json"
        content = '{"teams": {"backend": [{"name": "A", "role": "ab"}]}}'
        json_file.write_text(content)

        metadata = Source(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 2
        assert str(e) == "Config loading errors (2)"
        assert str(e.exceptions[0]) == (
            "  [teams.backend.0.name]  Value must have at least 2 characters\n"
            f"   ├── {content}\n"
            f"   │                                    ^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[1]) == (
            "  [teams.backend.0.role]  Value must have at least 3 characters\n"
            f"   ├── {content}\n"
            f"   │                                                 ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
