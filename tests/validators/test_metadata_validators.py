from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import JsonSource, V, load
from dature.errors import DatureConfigError
from dature.field_path import F


class TestMetadataValidatorsSuccess:
    def test_single_validator(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() >= 3,
            },
        )
        result = load(metadata, schema=Config)

        assert result.name == "Alice"

    def test_tuple_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080}')

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].port: (V > 0, V < 65536),
            },
        )
        result = load(metadata, schema=Config)

        assert result.port == 8080

    def test_multiple_fields(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str
            port: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice", "port": 8080}')

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() >= 3,
                F[Config].port: V > 0,
            },
        )
        result = load(metadata, schema=Config)

        assert result.name == "Alice"
        assert result.port == 8080


class TestMetadataValidatorsFailure:
    def test_single_validator_fails(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        content = '{"name": "Al"}'
        json_file.write_text(content)

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() >= 3,
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [name]  Value length must be greater than or equal to 3\n"
            '   ├── {"name": "<REDACTED>"}\n'
            "   │             ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_tuple_validator_fails(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int

        json_file = tmp_path / "config.json"
        content = '{"port": -1}'
        json_file.write_text(content)

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].port: (V > 0, V < 65536),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [port]  Value must be greater than 0\n"
            '   ├── {"port": <REDACTED>}\n'
            "   │            ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestMetadataValidatorsNested:
    def test_nested_field(self, tmp_path: Path):
        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database

        json_file = tmp_path / "config.json"
        json_file.write_text('{"database": {"host": "localhost", "port": 5432}}')

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].database.host: V.len() >= 1,
                F[Config].database.port: V > 0,
            },
        )
        result = load(metadata, schema=Config)

        assert result.database.host == "localhost"
        assert result.database.port == 5432

    def test_nested_field_fails(self, tmp_path: Path):
        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database

        json_file = tmp_path / "config.json"
        content = '{"database": {"host": "", "port": 5432}}'
        json_file.write_text(content)

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].database.host: V.len() >= 1,
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [database.host]  Value length must be greater than or equal to 1\n"
            '   ├── {"database": {"host": "", "port": <REDACTED>}}\n'
            "   │                         ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestMetadataValidatorsComplement:
    def test_metadata_validators_complement_annotated(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, V.len() >= 3]
            port: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice", "port": 8080}')

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() <= 50,
                F[Config].port: V > 0,
            },
        )
        result = load(metadata, schema=Config)

        assert result.name == "Alice"
        assert result.port == 8080

    def test_annotated_still_validates(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, V.len() >= 5]

        json_file = tmp_path / "config.json"
        content = '{"name": "Al"}'
        json_file.write_text(content)

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() <= 50,
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [name]  Value length must be greater than or equal to 5\n"
            '   ├── {"name": "<REDACTED>"}\n'
            "   │             ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_metadata_validator_fails_with_annotated_present(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, V.len() >= 3]

        json_file = tmp_path / "config.json"
        content = '{"name": "This is a very long name that exceeds the limit"}'
        json_file.write_text(content)

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() <= 10,
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [name]  Value length must be less than or equal to 10\n"
            '   ├── {"name": "<REDACTED>"}\n'
            "   │             ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_both_annotated_and_metadata_on_same_field_pass(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, V.len() >= 3]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() <= 10,
            },
        )
        result = load(metadata, schema=Config)

        assert result.name == "Alice"

    def test_annotated_fails_while_metadata_would_pass(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, V.len() >= 5]

        json_file = tmp_path / "config.json"
        content = '{"name": "AB"}'
        json_file.write_text(content)

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() <= 50,
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [name]  Value length must be greater than or equal to 5\n"
            '   ├── {"name": "<REDACTED>"}\n'
            "   │             ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_same_validator_type_in_annotated_and_metadata(self, tmp_path: Path):
        @dataclass
        class Config:
            port: Annotated[int, V >= 0]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080}')

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].port: V < 65536,
            },
        )
        result = load(metadata, schema=Config)

        assert result.port == 8080

    def test_same_validator_type_in_annotated_and_metadata_fails(self, tmp_path: Path):
        @dataclass
        class Config:
            port: Annotated[int, V >= 1024]

        json_file = tmp_path / "config.json"
        content = '{"port": 80}'
        json_file.write_text(content)

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].port: V < 65536,
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [port]  Value must be greater than or equal to 1024\n"
            '   ├── {"port": <REDACTED>}\n'
            "   │            ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_metadata_fails_while_annotated_passes(self, tmp_path: Path):
        @dataclass
        class Config:
            port: Annotated[int, V >= 0]

        json_file = tmp_path / "config.json"
        content = '{"port": 70000}'
        json_file.write_text(content)

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].port: V < 65536,
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, schema=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [port]  Value must be less than 65536\n"
            '   ├── {"port": <REDACTED>}\n'
            "   │            ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestMetadataValidatorsNone:
    def test_validators_none_works(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = JsonSource(file=json_file)
        result = load(metadata, schema=Config)

        assert result.name == "Alice"


class TestMetadataValidatorsWithRootValidators:
    def test_both_validators_and_root_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int
            user: str

        def validate_config(obj: Config) -> bool:
            if obj.port < 1024:
                return obj.user == "root"
            return True

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080, "user": "admin"}')

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].port: V >= 0,
            },
        )
        result = load(metadata, schema=Config, root_validators=(V.root(validate_config),))

        assert result.port == 8080
        assert result.user == "admin"


class TestMetadataValidatorsDecorator:
    def test_decorator_with_validators(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice", "age": 25}')

        @dataclass
        class Config:
            name: str
            age: int

        metadata = JsonSource(
            file=json_file,
            validators={
                F[Config].name: V.len() >= 2,
                F[Config].age: V >= 0,
            },
        )

        @load(metadata)
        @dataclass
        class Settings:
            name: str
            age: int

        s = Settings()
        assert s.name == "Alice"
        assert s.age == 25


class TestPerSourceFieldValidationBehavior:
    """Regression tests for per-source, per-field validation semantics."""

    def test_default_field_not_validated_per_source_only_at_end(self, tmp_path: Path):
        """Source provides only {a:1}; b has default 5 + validator V>0. Loading succeeds."""

        @dataclass
        class Cfg:
            a: Annotated[int, V > 0]
            b: Annotated[int, V > 0] = 5

        json_file = tmp_path / "cfg.json"
        json_file.write_text('{"a": 1}')

        result = load(JsonSource(file=json_file), schema=Cfg)

        assert result.a == 1
        assert result.b == 5

    def test_invalid_intermediate_value_fails_even_if_overwritten(self, tmp_path: Path):
        """Field x from source1 (valid) then source2 (invalid): raises because source2's value fails validator."""

        @dataclass
        class Cfg:
            x: Annotated[int, V > 0]

        file1 = tmp_path / "s1.json"
        file1.write_text('{"x": 1}')
        file2 = tmp_path / "s2.json"
        file2.write_text('{"x": -1}')

        with pytest.raises(DatureConfigError):
            load(JsonSource(file=file1), JsonSource(file=file2), schema=Cfg)
