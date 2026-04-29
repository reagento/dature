from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import pytest

from dature import JsonSource, V, load
from dature.errors import DatureConfigError


class TestMultipleFields:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, (V.len() >= 3) & (V.len() <= 50)]
            age: Annotated[int, (V >= 0) & (V <= 150)]
            tags: Annotated[list[str], (V.len() >= 1) & V.unique_items()]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice", "age": 30, "tags": ["python", "coding"]}')

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=Config)

        assert result.name == "Alice"
        assert result.age == 30
        assert result.tags == ["python", "coding"]

    def test_all_invalid(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, (V.len() >= 3) & (V.len() <= 50)]
            age: Annotated[int, (V >= 0) & (V <= 150)]
            tags: Annotated[list[str], (V.len() >= 1) & V.unique_items()]

        json_file = tmp_path / "config.json"
        content = '{"name": "AB", "age": 200, "tags": []}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 3
        assert str(e) == "Config loading errors (3)"
        assert str(e.exceptions[0]) == (
            "  [name]  Value length must be greater than or equal to 3\n"
            f"   ├── {content}\n"
            "   │             ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[1]) == (
            "  [age]  Value must be less than or equal to 150\n"
            f"   ├── {content}\n"
            "   │                         ^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[2]) == (
            "  [tags]  Value length must be greater than or equal to 1\n"
            f"   ├── {content}\n"
            "   │                                      ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestNestedDataclass:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Address:
            city: Annotated[str, V.len() >= 2]
            zip_code: Annotated[str, V.matches(r"^\d{5}$")]

        @dataclass
        class User:
            name: Annotated[str, V.len() >= 3]
            age: Annotated[int, V >= 18]
            address: Address

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"name": "Alice", "age": 30, "address": {"city": "NYC", "zip_code": "12345"}}',
        )

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=User)

        assert result.name == "Alice"
        assert result.age == 30
        assert result.address.city == "NYC"
        assert result.address.zip_code == "12345"

    def test_all_invalid(self, tmp_path: Path):
        @dataclass
        class Address:
            city: Annotated[str, V.len() >= 2]
            zip_code: Annotated[str, V.matches(r"^\d{5}$")]

        @dataclass
        class User:
            name: Annotated[str, V.len() >= 3]
            age: Annotated[int, V >= 18]
            address: Address

        json_file = tmp_path / "config.json"
        content = '{"name": "Al", "age": 15, "address": {"city": "N", "zip_code": "ABCDE"}}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=User)

        e = exc_info.value
        assert len(e.exceptions) == 4
        assert str(e) == "User loading errors (4)"
        assert str(e.exceptions[0]) == (
            "  [name]  Value length must be greater than or equal to 3\n"
            f"   ├── {content}\n"
            "   │             ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[1]) == (
            "  [age]  Value must be greater than or equal to 18\n"
            f"   ├── {content}\n"
            "   │                         ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[2]) == (
            "  [address.city]  Value length must be greater than or equal to 2\n"
            f"   ├── {content}\n"
            "   │                                                  ^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[3]) == (
            "  [address.zip_code]  Value must match pattern '^\\d{5}$'\n"
            f"   ├── {content}\n"
            "   │                                                                   ^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestCustomErrorMessage:
    def test_custom_error_message(self, tmp_path: Path):
        @dataclass
        class Config:
            age: Annotated[int, (V >= 18).with_error_message("Age must be 18 or older")]

        json_file = tmp_path / "config.json"
        content = '{"age": 15}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

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
            groups: Annotated[dict[str, list[dict[str, Any]]], V.len() >= 1]

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"groups": {"admins": [{"name": "Alice"}]}}',
        )

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=Config)

        assert result.groups == {"admins": [{"name": "Alice"}]}

    def test_raw_dict_field_validator_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            groups: Annotated[dict[str, list[dict[str, Any]]], V.len() >= 1]

        json_file = tmp_path / "config.json"
        content = '{"groups": {}}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [groups]  Value length must be greater than or equal to 1\n"
            f"   ├── {content}\n"
            "   │              ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_nested_dataclass_in_dict_list_success(self, tmp_path: Path):
        @dataclass
        class Member:
            name: Annotated[str, V.len() >= 2]
            role: Annotated[str, V.len() >= 3]

        @dataclass
        class Config:
            teams: dict[str, list[Member]]

        json_file = tmp_path / "config.json"
        json_file.write_text(
            '{"teams": {"backend": [{"name": "Alice", "role": "admin"}]}}',
        )

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=Config)

        assert result.teams["backend"][0].name == "Alice"
        assert result.teams["backend"][0].role == "admin"

    def test_nested_dataclass_in_dict_list_validation_fails(self, tmp_path: Path):
        @dataclass
        class Member:
            name: Annotated[str, V.len() >= 2]
            role: Annotated[str, V.len() >= 3]

        @dataclass
        class Config:
            teams: dict[str, list[Member]]

        json_file = tmp_path / "config.json"
        content = '{"teams": {"backend": [{"name": "A", "role": "ab"}]}}'
        json_file.write_text(content)

        metadata = JsonSource(file=json_file)

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 2
        assert str(e) == "Config loading errors (2)"
        assert str(e.exceptions[0]) == (
            "  [teams.backend.0.name]  Value length must be greater than or equal to 2\n"
            f"   ├── {content}\n"
            "   │                                    ^\n"
            f"   └── FILE '{json_file}', line 1"
        )
        assert str(e.exceptions[1]) == (
            "  [teams.backend.0.role]  Value length must be greater than or equal to 3\n"
            f"   ├── {content}\n"
            "   │                                                 ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )
