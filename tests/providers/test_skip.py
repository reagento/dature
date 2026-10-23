"""Tests for providers/skip.py."""

from dataclasses import dataclass
from typing import Any

import pytest
from adaptix import Retort

from dature.providers.model import ModelToDictProvider
from dature.providers.skip import SkipFieldProvider, filter_invalid_fields


@dataclass
class _HostPort:
    host: str
    port: int


@dataclass
class _Config:
    host: str
    port: int
    timeout: int


@pytest.fixture
def probe_retort() -> Retort:
    return Retort(strict_coercion=False, recipe=[SkipFieldProvider(), ModelToDictProvider()])


class TestFilterInvalidFields:
    @pytest.mark.parametrize(
        ("raw", "schema", "allowed", "expected_dict", "expected_paths"),
        [
            (
                {"host": "localhost", "port": 8080},
                _HostPort,
                None,
                {"host": "localhost", "port": 8080},
                [],
            ),
            (
                {"host": "localhost", "port": "abc"},
                _HostPort,
                None,
                {"host": "localhost"},
                ["port"],
            ),
            (
                {"host": "localhost", "port": "abc", "timeout": "bad"},
                _Config,
                {"port"},
                {"host": "localhost", "timeout": "bad"},
                ["port"],
            ),
        ],
        ids=["all_valid", "one_invalid", "allowed_fields_restricts_skip"],
    )
    def test_filters(
        self,
        probe_retort: Retort,
        raw: dict[str, Any],
        schema: type,
        allowed: set[str] | None,
        expected_dict: dict[str, Any],
        expected_paths: list[str],
    ):
        result = filter_invalid_fields(raw, probe_retort, schema, allowed)

        assert result.cleaned_dict == expected_dict
        assert result.skipped_paths == expected_paths

    def test_nested_field_invalid(self, probe_retort: Retort):
        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class NestedConfig:
            db: Database

        raw = {"db": {"host": "localhost", "port": "abc"}}

        result = filter_invalid_fields(raw, probe_retort, NestedConfig, None)

        assert result.cleaned_dict == {"db": {"host": "localhost"}}
        assert result.skipped_paths == ["db.port"]

    def test_non_dict_input(self, probe_retort: Retort):
        result = filter_invalid_fields("not a dict", probe_retort, _HostPort, None)

        assert result.cleaned_dict == "not a dict"
        assert result.skipped_paths == []
