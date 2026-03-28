from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import pytest

from dature import Source, load
from dature.errors.exceptions import DatureConfigError, FieldLoadError
from dature.sources_loader.yaml_ import Yaml11Loader, Yaml12Loader
from dature.validators.number import Ge, Le
from dature.validators.sequence import MinItems, UniqueItems
from dature.validators.string import MaxLength, MinLength, RegexPattern


@dataclass
class Address:
    city: Annotated[str, MinLength(value=2)]
    zip_code: Annotated[str, RegexPattern(pattern=r"^\d{5}$")]


@dataclass
class ErrorConfig:
    port: int
    host: str
    status: Literal["active", "inactive"]
    name: Annotated[str, MinLength(value=3), MaxLength(value=50)]
    email: Annotated[str, RegexPattern(pattern=r"^[\w.-]+@[\w.-]+\.\w+$")]
    age: Annotated[int, Ge(value=0), Le(value=150)]
    tags: Annotated[list[str], MinItems(value=1), UniqueItems()]
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
    name: Annotated[str, MinLength(value=3), MaxLength(value=50)]
    email: Annotated[str, RegexPattern(pattern=r"^[\w.-]+@[\w.-]+\.\w+$")]
    age: Annotated[int, Ge(value=0), Le(value=150)]
    tags: Annotated[list[str], MinItems(value=1), UniqueItems()]
    address: Address


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

ALL_SOURCES = [
    ("errors.json", {}),
    ("errors.json5", {}),
    ("errors.yaml", {}),
    ("errors.yaml", {"loader": Yaml11Loader}),
    ("errors.yaml", {"loader": Yaml12Loader}),
    ("errors.toml", {}),
    ("errors.ini", {"prefix": "config"}),
    ("errors.env", {}),
]

EXPECTED_LOAD_ERRORS = [
    (["port"], "invalid literal for int() with base 10: 'abc'"),
    (["host"], "Missing required field"),
    (["status"], "Invalid variant: 'unknown'"),
    (["address", "city"], "Value must have at least 2 characters"),
    (["address", "zip_code"], r"Value must match pattern '^\d{5}$'"),
]

EXPECTED_VALIDATION_ERRORS = [
    (["name"], "Value must have at least 3 characters"),
    (["email"], r"Value must match pattern '^[\w.-]+@[\w.-]+\.\w+$'"),
    (["age"], "Value must be less than or equal to 150"),
    (["tags"], "Value must have at least 1 items"),
    (["address", "city"], "Value must have at least 2 characters"),
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


@pytest.mark.parametrize(("fixture_file", "metadata_kwargs"), ALL_SOURCES)
def test_load_error_types(
    fixture_file: str,
    metadata_kwargs: dict[str, str],
) -> None:
    metadata = Source(file=str(FIXTURES_DIR / fixture_file), **metadata_kwargs)

    with pytest.raises(DatureConfigError) as exc_info:
        load(metadata, dataclass_=LoadErrorConfig)

    err = exc_info.value
    assert str(err) == f"LoadErrorConfig loading errors ({len(EXPECTED_LOAD_ERRORS)})"
    _assert_field_errors(err.exceptions, EXPECTED_LOAD_ERRORS)


@pytest.mark.parametrize(("fixture_file", "metadata_kwargs"), ALL_SOURCES)
def test_validation_error_types(
    fixture_file: str,
    metadata_kwargs: dict[str, str],
) -> None:
    metadata = Source(file=str(FIXTURES_DIR / fixture_file), **metadata_kwargs)

    with pytest.raises(DatureConfigError) as exc_info:
        load(metadata, dataclass_=ValidationErrorConfig)

    err = exc_info.value
    assert str(err) == f"ValidationErrorConfig loading errors ({len(EXPECTED_VALIDATION_ERRORS)})"
    _assert_field_errors(err.exceptions, EXPECTED_VALIDATION_ERRORS)
