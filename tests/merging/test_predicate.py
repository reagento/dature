"""Tests for predicate path extraction utilities."""

from dataclasses import dataclass

import pytest

from dature.field_path import F
from dature.merging.predicate import build_field_merge_map, extract_field_path


class TestExtractFieldPath:
    def test_single_field(self):
        @dataclass
        class Config:
            host: str

        assert extract_field_path(F[Config].host) == "host"

    def test_nested_field(self):
        @dataclass
        class Database:
            uri: str

        @dataclass
        class Config:
            database: Database

        assert extract_field_path(F[Config].database.uri) == "database.uri"

    def test_no_fields_raises_value_error(self):
        @dataclass
        class Config:
            host: str

        with pytest.raises(ValueError, match="at least one field name"):
            extract_field_path(F[Config])


class TestBuildFieldMergeMap:
    def test_builds_map_from_rules(self):
        @dataclass
        class Config:
            host: str
            port: int
            tags: list[str]

        field_merges = {
            F[Config].host: "first_wins",
            F[Config].tags: "append",
        }

        result = build_field_merge_map(field_merges)

        assert result.enum_map == {
            "host": "first_wins",
            "tags": "append",
        }
        assert result.callable_map == {}

    def test_empty_rules(self):
        result = build_field_merge_map({})
        assert result.enum_map == {}
        assert result.callable_map == {}

    def test_nested_field_path(self):
        @dataclass
        class Database:
            host: str

        @dataclass
        class Config:
            database: Database

        field_merges = {F[Config].database.host: "last_wins"}

        result = build_field_merge_map(field_merges)

        assert result.enum_map == {"database.host": "last_wins"}
        assert result.callable_map == {}

    def test_callable_strategy(self):
        @dataclass
        class Config:
            host: str
            score: int

        field_merges = {
            F[Config].host: "first_wins",
            F[Config].score: sum,
        }

        result = build_field_merge_map(field_merges)

        assert result.enum_map == {"host": "first_wins"}
        assert result.callable_map == {"score": sum}

    def test_validates_owner_mismatch(self):
        @dataclass
        class Config:
            host: str

        @dataclass
        class Other:
            host: str

        field_merges = {F[Other].host: "first_wins"}

        with pytest.raises(TypeError) as exc_info:
            build_field_merge_map(field_merges, dataclass_=Config)
        assert str(exc_info.value) == "FieldPath owner 'Other' does not match target dataclass 'Config'"


class TestExtractFieldPathWithOwnerValidation:
    def test_validates_owner_mismatch(self):
        @dataclass
        class Config:
            host: str

        with pytest.raises(TypeError) as exc_info:
            extract_field_path(F["Other"].host, dataclass_=Config)
        assert str(exc_info.value) == "FieldPath owner 'Other' does not match target dataclass 'Config'"

    def test_passes_with_correct_string_owner(self):
        @dataclass
        class Config:
            host: str

        assert extract_field_path(F["Config"].host, dataclass_=Config) == "host"
