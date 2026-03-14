from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Literal

import pytest

from dature import LoadMetadata, load
from dature.errors.exceptions import DatureConfigError
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


def _load_error_message(p: str) -> str:
    return dedent("""\
        LoadErrorConfig loading errors (5)

          [port]  Bad string format
           └── FILE '{path}', line 2
               "port": "abc",

          [host]  Missing required field
           └── FILE '{path}'

          [status]  Invalid variant: 'unknown'
           └── FILE '{path}', line 3
               "status": "unknown",

          [address.city]  Value must have at least 2 characters
           └── FILE '{path}', line 9
               "city": "N",

          [address.zip_code]  Value must match pattern '^\\d{5}$'
           └── FILE '{path}', line 10
               "zip_code": "ABCDE"
        """).replace("{path}", p)


def _validation_error_message(p: str) -> str:
    return dedent("""\
        ValidationErrorConfig loading errors (6)

          [name]  Value must have at least 3 characters
           └── FILE '{path}', line 4
               "name": "AB",

          [email]  Value must match pattern '^[\\w.-]+@[\\w.-]+\\.\\w+$'
           └── FILE '{path}', line 5
               "email": "not-an-email",

          [age]  Value must be less than or equal to 150
           └── FILE '{path}', line 6
               "age": 200,

          [tags]  Value must have at least 1 items
           └── FILE '{path}', line 7
               "tags": [],

          [address.city]  Value must have at least 2 characters
           └── FILE '{path}', line 9
               "city": "N",

          [address.zip_code]  Value must match pattern '^\\d{5}$'
           └── FILE '{path}', line 10
               "zip_code": "ABCDE"
        """).replace("{path}", p)


EXPECTED_LOAD_MESSAGES: dict[str, str] = {}
EXPECTED_VALIDATION_MESSAGES: dict[str, str] = {}


def _file(name: str) -> str:
    return str(FIXTURES_DIR / name)


# --- json ---
EXPECTED_LOAD_MESSAGES["json"] = _load_error_message(_file("errors.json"))
EXPECTED_VALIDATION_MESSAGES["json"] = _validation_error_message(_file("errors.json"))

# --- json5 ---
_json5_path = _file("errors.json5")
EXPECTED_LOAD_MESSAGES["json5"] = dedent(f"""\
    LoadErrorConfig loading errors (5)

      [port]  Bad string format
       └── FILE '{_json5_path}', line 3
           port: "abc",

      [host]  Missing required field
       └── FILE '{_json5_path}'

      [status]  Invalid variant: 'unknown'
       └── FILE '{_json5_path}', line 5
           status: "unknown",

      [address.city]  Value must have at least 2 characters
       └── FILE '{_json5_path}', line 16
           city: "N",

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── FILE '{_json5_path}', line 17
           zip_code: "ABCDE",
    """)

EXPECTED_VALIDATION_MESSAGES["json5"] = dedent(f"""\
    ValidationErrorConfig loading errors (6)

      [name]  Value must have at least 3 characters
       └── FILE '{_json5_path}', line 7
           name: "AB",

      [email]  Value must match pattern '^[\\w.-]+@[\\w.-]+\\.\\w+$'
       └── FILE '{_json5_path}', line 9
           email: "not-an-email",

      [age]  Value must be less than or equal to 150
       └── FILE '{_json5_path}', line 11
           age: 200,

      [tags]  Value must have at least 1 items
       └── FILE '{_json5_path}', line 13
           tags: [],

      [address.city]  Value must have at least 2 characters
       └── FILE '{_json5_path}', line 16
           city: "N",

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── FILE '{_json5_path}', line 17
           zip_code: "ABCDE",
    """)

# --- yaml ---
_yaml_path = _file("errors.yaml")
EXPECTED_LOAD_MESSAGES["yaml"] = dedent(f"""\
    LoadErrorConfig loading errors (5)

      [port]  Bad string format
       └── FILE '{_yaml_path}', line 1
           port: "abc"

      [host]  Missing required field
       └── FILE '{_yaml_path}'

      [status]  Invalid variant: 'unknown'
       └── FILE '{_yaml_path}', line 2
           status: "unknown"

      [address.city]  Value must have at least 2 characters
       └── FILE '{_yaml_path}', line 8
           city: "N"

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── FILE '{_yaml_path}', line 9
           zip_code: "ABCDE"
    """)
EXPECTED_VALIDATION_MESSAGES["yaml"] = dedent(f"""\
    ValidationErrorConfig loading errors (6)

      [name]  Value must have at least 3 characters
       └── FILE '{_yaml_path}', line 3
           name: "AB"

      [email]  Value must match pattern '^[\\w.-]+@[\\w.-]+\\.\\w+$'
       └── FILE '{_yaml_path}', line 4
           email: "not-an-email"

      [age]  Value must be less than or equal to 150
       └── FILE '{_yaml_path}', line 5
           age: 200

      [tags]  Value must have at least 1 items
       └── FILE '{_yaml_path}', line 6
           tags: []

      [address.city]  Value must have at least 2 characters
       └── FILE '{_yaml_path}', line 8
           city: "N"

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── FILE '{_yaml_path}', line 9
           zip_code: "ABCDE"
    """)

# --- toml ---
_toml_path = _file("errors.toml")
EXPECTED_LOAD_MESSAGES["toml"] = dedent(f"""\
    LoadErrorConfig loading errors (5)

      [port]  Bad string format
       └── FILE '{_toml_path}', line 1
           port = "abc"

      [host]  Missing required field
       └── FILE '{_toml_path}'

      [status]  Invalid variant: 'unknown'
       └── FILE '{_toml_path}', line 2
           status = "unknown"

      [address.city]  Value must have at least 2 characters
       └── FILE '{_toml_path}', line 9
           city = "N"

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── FILE '{_toml_path}', line 10
           zip_code = "ABCDE"
    """)
EXPECTED_VALIDATION_MESSAGES["toml"] = dedent(f"""\
    ValidationErrorConfig loading errors (6)

      [name]  Value must have at least 3 characters
       └── FILE '{_toml_path}', line 3
           name = "AB"

      [email]  Value must match pattern '^[\\w.-]+@[\\w.-]+\\.\\w+$'
       └── FILE '{_toml_path}', line 4
           email = "not-an-email"

      [age]  Value must be less than or equal to 150
       └── FILE '{_toml_path}', line 5
           age = 200

      [tags]  Value must have at least 1 items
       └── FILE '{_toml_path}', line 6
           tags = []

      [address.city]  Value must have at least 2 characters
       └── FILE '{_toml_path}', line 9
           city = "N"

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── FILE '{_toml_path}', line 10
           zip_code = "ABCDE"
    """)

# --- ini ---
_ini_path = _file("errors.ini")
EXPECTED_LOAD_MESSAGES["ini"] = dedent(f"""\
    LoadErrorConfig loading errors (5)

      [port]  Bad string format
       └── FILE '{_ini_path}', line 2
           port = abc

      [host]  Missing required field
       └── FILE '{_ini_path}'

      [status]  Invalid variant: 'unknown'
       └── FILE '{_ini_path}', line 3
           status = unknown

      [address.city]  Value must have at least 2 characters
       └── FILE '{_ini_path}', line 10
           city = N

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── FILE '{_ini_path}', line 11
           zip_code = ABCDE
    """)
EXPECTED_VALIDATION_MESSAGES["ini"] = dedent(f"""\
    ValidationErrorConfig loading errors (6)

      [name]  Value must have at least 3 characters
       └── FILE '{_ini_path}', line 4
           name = AB

      [email]  Value must match pattern '^[\\w.-]+@[\\w.-]+\\.\\w+$'
       └── FILE '{_ini_path}', line 5
           email = not-an-email

      [age]  Value must be less than or equal to 150
       └── FILE '{_ini_path}', line 6
           age = 200

      [tags]  Value must have at least 1 items
       └── FILE '{_ini_path}', line 7
           tags = []

      [address.city]  Value must have at least 2 characters
       └── FILE '{_ini_path}', line 10
           city = N

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── FILE '{_ini_path}', line 11
           zip_code = ABCDE
    """)

# --- env ---
_env_path = _file("errors.env")
EXPECTED_LOAD_MESSAGES["env"] = dedent(f"""\
    LoadErrorConfig loading errors (5)

      [port]  Bad string format
       └── ENV FILE '{_env_path}', line 1
           PORT=abc

      [host]  Missing required field
       └── ENV FILE '{_env_path}'

      [status]  Invalid variant: 'unknown'
       └── ENV FILE '{_env_path}', line 2
           STATUS=unknown

      [address.city]  Value must have at least 2 characters
       └── ENV FILE '{_env_path}', line 7
           ADDRESS__CITY=N

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── ENV FILE '{_env_path}', line 8
           ADDRESS__ZIP_CODE=ABCDE
    """)
EXPECTED_VALIDATION_MESSAGES["env"] = dedent(f"""\
    ValidationErrorConfig loading errors (6)

      [name]  Value must have at least 3 characters
       └── ENV FILE '{_env_path}', line 3
           NAME=AB

      [email]  Value must match pattern '^[\\w.-]+@[\\w.-]+\\.\\w+$'
       └── ENV FILE '{_env_path}', line 4
           EMAIL=not-an-email

      [age]  Value must be less than or equal to 150
       └── ENV FILE '{_env_path}', line 5
           AGE=200

      [tags]  Value must have at least 1 items
       └── ENV FILE '{_env_path}', line 6
           TAGS=[]

      [address.city]  Value must have at least 2 characters
       └── ENV FILE '{_env_path}', line 7
           ADDRESS__CITY=N

      [address.zip_code]  Value must match pattern '^\\d{{5}}$'
       └── ENV FILE '{_env_path}', line 8
           ADDRESS__ZIP_CODE=ABCDE
    """)


def _get_format_key(fixture_file: str) -> str:
    suffix = Path(fixture_file).suffix.lstrip(".")
    if suffix == "json5":
        return "json5"
    return suffix


@pytest.mark.parametrize(("fixture_file", "metadata_kwargs"), ALL_SOURCES)
def test_load_error_types(
    fixture_file: str,
    metadata_kwargs: dict[str, str],
) -> None:
    path = str(FIXTURES_DIR / fixture_file)
    metadata = LoadMetadata(file_=path, **metadata_kwargs)

    with pytest.raises(DatureConfigError) as exc_info:
        load(metadata, LoadErrorConfig)

    fmt = _get_format_key(fixture_file)
    assert str(exc_info.value) == EXPECTED_LOAD_MESSAGES[fmt]


@pytest.mark.parametrize(("fixture_file", "metadata_kwargs"), ALL_SOURCES)
def test_validation_error_types(
    fixture_file: str,
    metadata_kwargs: dict[str, str],
) -> None:
    path = str(FIXTURES_DIR / fixture_file)
    metadata = LoadMetadata(file_=path, **metadata_kwargs)

    with pytest.raises(DatureConfigError) as exc_info:
        load(metadata, ValidationErrorConfig)

    fmt = _get_format_key(fixture_file)
    assert str(exc_info.value) == EXPECTED_VALIDATION_MESSAGES[fmt]
