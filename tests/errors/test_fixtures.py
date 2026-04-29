from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import pytest

from dature import EnvFileSource, IniSource, Json5Source, JsonSource, Toml11Source, V, Yaml11Source, Yaml12Source, load
from dature.errors import DatureConfigError, FieldLoadError


@dataclass
class Address:
    city: Annotated[str, V.len() >= 2]
    zip_code: Annotated[str, V.matches(r"^\d{5}$")]


@dataclass
class ErrorConfig:
    port: int
    host: str
    status: Literal["active", "inactive"]
    name: Annotated[str, (V.len() >= 3) & (V.len() <= 50)]
    email: Annotated[str, V.matches(r"^[\w.-]+@[\w.-]+\.\w+$")]
    age: Annotated[int, (V >= 0) & (V <= 150)]
    tags: Annotated[list[str], (V.len() >= 1) & V.unique_items()]
    address: Address


@dataclass
class LoadErrorConfig:
    port: int
    host: str
    status: Literal["active", "inactive"]
    name: str
    email: str
    age: int
    tags: list[str]
    address: Address


@dataclass
class ValidationErrorConfig:
    name: Annotated[str, (V.len() >= 3) & (V.len() <= 50)]
    email: Annotated[str, V.matches(r"^[\w.-]+@[\w.-]+\.\w+$")]
    age: Annotated[int, (V >= 0) & (V <= 150)]
    tags: Annotated[list[str], (V.len() >= 1) & V.unique_items()]
    address: Address


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

ALL_SOURCES = [
    ("errors.json", JsonSource, {}),
    ("errors.json5", Json5Source, {}),
    ("errors.yaml", Yaml11Source, {}),
    ("errors.yaml", Yaml12Source, {}),
    ("errors.toml", Toml11Source, {}),
    ("errors.ini", IniSource, {"prefix": "config"}),
    ("errors.env", EnvFileSource, {}),
]

EXPECTED_LOAD_ERRORS = [
    (["port"], "invalid literal for int() with base 10: 'abc'"),
    (["host"], "Missing required field"),
    (["status"], "Invalid variant: 'unknown'"),
    (["address", "city"], "Value length must be greater than or equal to 2"),
    (["address", "zip_code"], r"Value must match pattern '^\d{5}$'"),
]

EXPECTED_VALIDATION_ERRORS = [
    (["name"], "Value length must be greater than or equal to 3"),
    (["email"], r"Value must match pattern '^[\w.-]+@[\w.-]+\.\w+$'"),
    (["age"], "Value must be less than or equal to 150"),
    (["tags"], "Value length must be greater than or equal to 1"),
    (["address", "city"], "Value length must be greater than or equal to 2"),
    (["address", "zip_code"], r"Value must match pattern '^\d{5}$'"),
]


def _assert_field_errors(
    exceptions: tuple[Exception, ...],
    expected: list[tuple[list[str], str]],
) -> None:
    assert len(exceptions) == len(expected)
    for exc, (path, message) in zip(exceptions, expected, strict=True):
        assert isinstance(exc, FieldLoadError)
        assert exc.field_path == path
        assert exc.message == message


@pytest.mark.parametrize(("fixture_file", "source_class", "source_kwargs"), ALL_SOURCES)
def test_load_error_types(
    fixture_file: str,
    source_class: type,
    source_kwargs: dict[str, str],
) -> None:
    metadata = source_class(file=str(FIXTURES_DIR / fixture_file), **source_kwargs)

    with pytest.raises(DatureConfigError) as exc_info:
        load(metadata, schema=LoadErrorConfig)

    err = exc_info.value
    assert str(err) == f"LoadErrorConfig loading errors ({len(EXPECTED_LOAD_ERRORS)})"
    _assert_field_errors(err.exceptions, EXPECTED_LOAD_ERRORS)


@pytest.mark.parametrize(("fixture_file", "source_class", "source_kwargs"), ALL_SOURCES)
def test_validation_error_types(
    fixture_file: str,
    source_class: type,
    source_kwargs: dict[str, str],
) -> None:
    metadata = source_class(file=str(FIXTURES_DIR / fixture_file), **source_kwargs)

    with pytest.raises(DatureConfigError) as exc_info:
        load(metadata, schema=ValidationErrorConfig)

    err = exc_info.value
    assert str(err) == f"ValidationErrorConfig loading errors ({len(EXPECTED_VALIDATION_ERRORS)})"
    _assert_field_errors(err.exceptions, EXPECTED_VALIDATION_ERRORS)
