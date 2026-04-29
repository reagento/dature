"""Integration tests for V.each — per-element validation with trailed field paths."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import JsonSource, V, load
from dature.errors import DatureConfigError, FieldLoadError


def _load_tags(tmp_path: Path, content: str, predicate):
    @dataclass
    class Config:
        tags: Annotated[list[str], predicate]

    json_file = tmp_path / "config.json"
    json_file.write_text(content)

    with pytest.raises(DatureConfigError) as exc_info:
        load(JsonSource(file=json_file), schema=Config)

    return exc_info.value


class TestEachHappyPath:
    def test_empty_list_passes(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], V.each(V.len() >= 3)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": []}')

        result = load(JsonSource(file=json_file), schema=Config)
        assert result.tags == []

    def test_all_elements_valid(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], V.each(V.len() >= 3)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": ["abc", "abcd"]}')

        result = load(JsonSource(file=json_file), schema=Config)
        assert result.tags == ["abc", "abcd"]


class TestEachReportsPerElementFieldPath:
    def test_single_bad_element_at_index(self, tmp_path: Path):
        err = _load_tags(
            tmp_path,
            '{"tags": ["abc", "ab", "abcd"]}',
            V.each(V.len() >= 3),
        )

        assert len(err.exceptions) == 1

        exc = err.exceptions[0]

        assert isinstance(exc, FieldLoadError)
        assert exc.field_path == ["tags", "1"]
        assert exc.message == "Value length must be greater than or equal to 3"

    def test_multiple_bad_elements(self, tmp_path: Path):
        err = _load_tags(
            tmp_path,
            '{"tags": ["ab", "okay", "x"]}',
            V.each(V.len() >= 3),
        )

        field_errors = [exc for exc in err.exceptions if isinstance(exc, FieldLoadError)]
        assert [exc.field_path for exc in field_errors] == [["tags", "0"], ["tags", "2"]]


class TestEachWithComposedInner:
    def test_and_inner(self, tmp_path: Path):
        inner = (V.len() >= 2) & V.matches(r"^[a-z]+$")

        @dataclass
        class Config:
            tags: Annotated[list[str], V.each(inner)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": ["ab", "cde"]}')

        result = load(JsonSource(file=json_file), schema=Config)
        assert result.tags == ["ab", "cde"]

    def test_and_inner_failure(self, tmp_path: Path):
        err = _load_tags(
            tmp_path,
            '{"tags": ["ab", "CD", "ef"]}',
            V.each((V.len() >= 2) & V.matches(r"^[a-z]+$")),
        )

        field_errors = [exc for exc in err.exceptions if isinstance(exc, FieldLoadError)]
        assert [exc.field_path for exc in field_errors] == [["tags", "1"]]


class TestEachWithOuterPredicates:
    def test_outer_len_and_each(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[list[str], (V.len() >= 1) & V.each(V.len() >= 3)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": ["abcd"]}')

        result = load(JsonSource(file=json_file), schema=Config)
        assert result.tags == ["abcd"]

    def test_outer_fails_independently(self, tmp_path: Path):
        # Empty list: outer len >= 1 fails; each passes (no elements)
        err = _load_tags(
            tmp_path,
            '{"tags": []}',
            (V.len() >= 1) & V.each(V.len() >= 3),
        )

        field_errors = [exc for exc in err.exceptions if isinstance(exc, FieldLoadError)]
        assert [exc.field_path for exc in field_errors] == [["tags"]]
        assert [exc.message for exc in field_errors] == ["Value length must be greater than or equal to 1"]


class TestEachOnTupleAndSet:
    def test_tuple(self, tmp_path: Path):
        @dataclass
        class Config:
            tags: Annotated[tuple[str, ...], V.each(V.len() >= 3)]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"tags": ["abc", "def"]}')

        result = load(JsonSource(file=json_file), schema=Config)
        assert result.tags == ("abc", "def")


class TestNestedDataclassesInList:
    def test_nested_predicates_still_fire(self, tmp_path: Path):
        @dataclass
        class Member:
            name: Annotated[str, V.len() >= 2]

        @dataclass
        class Config:
            members: list[Member]

        json_file = tmp_path / "config.json"
        json_file.write_text('{"members": [{"name": "A"}, {"name": "Bob"}]}')

        with pytest.raises(DatureConfigError) as exc_info:
            load(JsonSource(file=json_file), schema=Config)

        err = exc_info.value
        assert len(err.exceptions) == 1

        exc = err.exceptions[0]
        assert isinstance(exc, FieldLoadError)
        assert exc.field_path == ["members", "0", "name"]
