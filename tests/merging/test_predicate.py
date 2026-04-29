"""Tests for build_field_merge_map."""

from dataclasses import dataclass

import pytest

from dature.field_path import F
from dature.merging.predicate import build_field_merge_map
from dature.strategies.field import (
    FieldAppend,
    FieldFirstWins,
    FieldLastWins,
    FieldMergeStrategy,
)


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

        assert set(result.keys()) == {"host", "tags"}
        assert isinstance(result["host"], FieldFirstWins)
        assert isinstance(result["tags"], FieldAppend)

    def test_empty_rules(self):
        result = build_field_merge_map({})
        assert result == {}

    def test_nested_field_path(self):
        @dataclass
        class Database:
            host: str

        @dataclass
        class Config:
            database: Database

        field_merges = {F[Config].database.host: "last_wins"}

        result = build_field_merge_map(field_merges)

        assert set(result.keys()) == {"database.host"}
        assert isinstance(result["database.host"], FieldLastWins)

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

        assert set(result.keys()) == {"host", "score"}
        assert isinstance(result["host"], FieldFirstWins)
        assert result["score"] is sum  # callable kept as-is

    def test_field_strategy_instance(self):
        @dataclass
        class Config:
            host: str

        field_merges = {F[Config].host: FieldLastWins()}

        result = build_field_merge_map(field_merges)

        assert isinstance(result["host"], FieldLastWins)
        assert isinstance(result["host"], FieldMergeStrategy)

    def test_validates_owner_mismatch(self):
        @dataclass
        class Config:
            host: str

        @dataclass
        class Other:
            host: str

        field_merges = {F[Other].host: "first_wins"}

        with pytest.raises(TypeError) as exc_info:
            build_field_merge_map(field_merges, schema=Config)
        assert str(exc_info.value) == "FieldPath owner 'Other' does not match target dataclass 'Config'"
