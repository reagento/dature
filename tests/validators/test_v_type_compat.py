"""Eager type-compatibility checks for V predicates.

All of these assertions must fire **before** any configuration data is read —
they're raised during retort construction, so a bad schema fails fast with a
helpful error naming the field and the required protocol.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import pytest

from dature import JsonSource, V, load
from dature.errors import ValidatorTypeError
from dature.validators.base import extract_and_check_validators


def _assert_retort_build_fails(schema: type, tmp_path: Path, match: str) -> None:
    """Verify that the error fires before any data is read.

    We point the source at a file that doesn't exist — if validation reached
    loading, the user would see FileNotFoundError, not ValidatorTypeError.
    """
    missing_file = tmp_path / "does-not-exist.json"

    with pytest.raises(ValidatorTypeError, match=match):
        load(JsonSource(file=missing_file), schema=schema)


class TestLenRequiresSized:
    @pytest.mark.parametrize("bad_type", [int, float, bool])
    def test_rejects_unsized(self, bad_type: Any):
        with pytest.raises(ValidatorTypeError, match=r"V\.len\(\)"):
            extract_and_check_validators(
                Annotated[bad_type, V.len() >= 3],
                field_path=["x"],
            )

    @pytest.mark.parametrize(
        "field_type",
        [str, bytes, list[int], tuple[int, ...], set[int], frozenset[int], dict[str, int]],
    )
    def test_accepts_sized(self, field_type: Any):
        extracted = extract_and_check_validators(
            Annotated[field_type, V.len() >= 1],
            field_path=["x"],
        )
        assert len(extracted) == 1

    def test_error_mentions_sized_protocol(self):
        with pytest.raises(ValidatorTypeError, match=r"collections\.abc\.Sized"):
            extract_and_check_validators(
                Annotated[int, V.len() >= 3],
                field_path=["port"],
            )


class TestMatchesRequiresStr:
    @pytest.mark.parametrize("bad_type", [int, list[str], bytes])
    def test_rejects_non_str(self, bad_type: Any):
        with pytest.raises(ValidatorTypeError, match=r"V\.matches"):
            extract_and_check_validators(
                Annotated[bad_type, V.matches(r"^.+$")],
                field_path=["x"],
            )

    def test_accepts_str(self):
        extracted = extract_and_check_validators(
            Annotated[str, V.matches(r"^.+$")],
            field_path=["x"],
        )
        assert len(extracted) == 1


class TestUniqueItemsRequiresCollection:
    @pytest.mark.parametrize("bad_type", [int, float, bool])
    def test_rejects_scalars(self, bad_type: Any):
        with pytest.raises(ValidatorTypeError, match=r"V\.unique_items"):
            extract_and_check_validators(
                Annotated[bad_type, V.unique_items()],
                field_path=["x"],
            )

    @pytest.mark.parametrize("field_type", [list[int], tuple[int, ...], set[int], frozenset[int]])
    def test_accepts_collections(self, field_type: Any):
        extracted = extract_and_check_validators(
            Annotated[field_type, V.unique_items()],
            field_path=["x"],
        )
        assert len(extracted) == 1


class TestEachRequiresIterable:
    def test_rejects_int_outer(self, tmp_path: Path):
        @dataclass
        class Config:
            x: Annotated[int, V.each(V >= 0)]

        _assert_retort_build_fails(Config, tmp_path, r"V\.each")

    def test_rejects_incompatible_inner(self):
        # list[int] supports iteration, but V.len() requires elements to be Sized — int is not.
        with pytest.raises(ValidatorTypeError, match=r"V\.len\(\)"):
            extract_and_check_validators(
                Annotated[list[int], V.each(V.len() >= 3)],
                field_path=["tags"],
            )

    def test_accepts_valid(self):
        extracted = extract_and_check_validators(
            Annotated[list[str], V.each(V.len() >= 3)],
            field_path=["tags"],
        )
        assert len(extracted) == 1


class TestFieldPathInErrorMessage:
    def test_field_path_present(self, tmp_path: Path):
        @dataclass
        class Config:
            nested_port_field: Annotated[int, V.len() >= 3]

        with pytest.raises(ValidatorTypeError) as exc_info:
            load(JsonSource(file=tmp_path / "missing.json"), schema=Config)

        assert "nested_port_field" in exc_info.value.message
        assert exc_info.value.field_path == ["nested_port_field"]


class TestCompositeDelegatesToChildren:
    def test_and_propagates_error(self):
        with pytest.raises(ValidatorTypeError, match=r"V\.len\(\)"):
            extract_and_check_validators(
                Annotated[int, (V >= 0) & (V.len() >= 3)],
                field_path=["x"],
            )

    def test_or_propagates_error(self):
        with pytest.raises(ValidatorTypeError, match=r"V\.matches"):
            extract_and_check_validators(
                Annotated[int, (V > 0) | V.matches(r"^a$")],
                field_path=["x"],
            )

    def test_not_propagates_error(self):
        with pytest.raises(ValidatorTypeError, match=r"V\.unique_items"):
            extract_and_check_validators(
                Annotated[int, ~V.unique_items()],
                field_path=["x"],
            )


class TestEagerBeforeDataRead:
    def test_error_raised_before_file_access(self, tmp_path: Path):
        """If eager check worked, the error names V.len, not FileNotFoundError."""

        @dataclass
        class Config:
            x: Annotated[int, V.len() >= 3]

        missing_file = tmp_path / "does-not-exist.json"

        with pytest.raises(ValidatorTypeError):
            load(JsonSource(file=missing_file), schema=Config)
