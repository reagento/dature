from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import Source, load
from dature.errors.exceptions import DatureConfigError
from dature.field_path import F
from dature.validators.number import Ge, Gt, Lt
from dature.validators.root import RootValidator
from dature.validators.string import MaxLength, MinLength


class TestMetadataValidatorsSuccess:
    def test_single_validator(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MinLength(3),
            },
        )
        result = load(metadata, dataclass_=Config)

        assert result.name == "Alice"

    def test_tuple_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080}')

        metadata = Source(
            file=json_file,
            validators={
                F[Config].port: (Gt(0), Lt(65536)),
            },
        )
        result = load(metadata, dataclass_=Config)

        assert result.port == 8080

    def test_multiple_fields(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str
            port: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice", "port": 8080}')

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MinLength(3),
                F[Config].port: Gt(0),
            },
        )
        result = load(metadata, dataclass_=Config)

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

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MinLength(3),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at least 3 characters\n"
            f"   ├── {content}\n"
            f"   │             ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_tuple_validator_fails(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int

        json_file = tmp_path / "config.json"
        content = '{"port": -1}'
        json_file.write_text(content)

        metadata = Source(
            file=json_file,
            validators={
                F[Config].port: (Gt(0), Lt(65536)),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [port]  Value must be greater than 0\n"
            f"   ├── {content}\n"
            f"   │            ^^\n"
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

        metadata = Source(
            file=json_file,
            validators={
                F[Config].database.host: MinLength(1),
                F[Config].database.port: Gt(0),
            },
        )
        result = load(metadata, dataclass_=Config)

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

        metadata = Source(
            file=json_file,
            validators={
                F[Config].database.host: MinLength(1),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [database.host]  Value must have at least 1 characters\n"
            f"   ├── {content}\n"
            "   │                         ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestMetadataValidatorsComplement:
    def test_metadata_validators_complement_annotated(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(3)]
            port: int

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice", "port": 8080}')

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MaxLength(50),
                F[Config].port: Gt(0),
            },
        )
        result = load(metadata, dataclass_=Config)

        assert result.name == "Alice"
        assert result.port == 8080

    def test_annotated_still_validates(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(5)]

        json_file = tmp_path / "config.json"
        content = '{"name": "Al"}'
        json_file.write_text(content)

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MaxLength(50),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at least 5 characters\n"
            f"   ├── {content}\n"
            f"   │             ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_metadata_validator_fails_with_annotated_present(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(3)]

        json_file = tmp_path / "config.json"
        content = '{"name": "This is a very long name that exceeds the limit"}'
        json_file.write_text(content)

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MaxLength(10),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at most 10 characters\n"
            f"   ├── {content}\n"
            f"   │             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_both_annotated_and_metadata_on_same_field_pass(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(3)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MaxLength(10),
            },
        )
        result = load(metadata, dataclass_=Config)

        assert result.name == "Alice"

    def test_annotated_fails_while_metadata_would_pass(self, tmp_path: Path):
        @dataclass
        class Config:
            name: Annotated[str, MinLength(5)]

        json_file = tmp_path / "config.json"
        content = '{"name": "AB"}'
        json_file.write_text(content)

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MaxLength(50),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [name]  Value must have at least 5 characters\n"
            f"   ├── {content}\n"
            f"   │             ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_same_validator_type_in_annotated_and_metadata(self, tmp_path: Path):
        @dataclass
        class Config:
            port: Annotated[int, Ge(0)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080}')

        metadata = Source(
            file=json_file,
            validators={
                F[Config].port: Lt(65536),
            },
        )
        result = load(metadata, dataclass_=Config)

        assert result.port == 8080

    def test_same_validator_type_in_annotated_and_metadata_fails(self, tmp_path: Path):
        @dataclass
        class Config:
            port: Annotated[int, Ge(1024)]

        json_file = tmp_path / "config.json"
        content = '{"port": 80}'
        json_file.write_text(content)

        metadata = Source(
            file=json_file,
            validators={
                F[Config].port: Lt(65536),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            "  [port]  Value must be greater than or equal to 1024\n"
            f"   ├── {content}\n"
            f"   │            ^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    def test_metadata_fails_while_annotated_passes(self, tmp_path: Path):
        @dataclass
        class Config:
            port: Annotated[int, Ge(0)]

        json_file = tmp_path / "config.json"
        content = '{"port": 70000}'
        json_file.write_text(content)

        metadata = Source(
            file=json_file,
            validators={
                F[Config].port: Lt(65536),
            },
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, dataclass_=Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (
            f"  [port]  Value must be less than 65536\n"
            f"   ├── {content}\n"
            f"   │            ^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )


class TestMetadataValidatorsNone:
    def test_validators_none_works(self, tmp_path: Path):
        @dataclass
        class Config:
            name: str

        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Alice"}')

        metadata = Source(file=json_file)
        result = load(metadata, dataclass_=Config)

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

        metadata = Source(
            file=json_file,
            root_validators=(RootValidator(validate_config),),
            validators={
                F[Config].port: Ge(0),
            },
        )
        result = load(metadata, dataclass_=Config)

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

        metadata = Source(
            file=json_file,
            validators={
                F[Config].name: MinLength(2),
                F[Config].age: Ge(0),
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
