"""Tests for per-field merge strategies (field_merges)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from dature import JsonSource, load
from dature.errors import MergeConflictError
from dature.field_path import F
from dature.types import FieldMergeStrategyName


class TestFieldMergesFunction:
    def test_first_wins_per_field_with_global_last_wins(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "default-host", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "override-host", "port": 9090}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            strategy="last_wins",
            field_merges={F[Config].host: "first_wins"},
        )

        assert result.host == "default-host"
        assert result.port == 9090

    def test_last_wins_per_field_with_global_first_wins(self, tmp_path: Path):
        first = tmp_path / "first.json"
        first.write_text('{"host": "first-host", "port": 1000}')

        second = tmp_path / "second.json"
        second.write_text('{"host": "second-host", "port": 2000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=first),
            JsonSource(file=second),
            schema=Config,
            strategy="first_wins",
            field_merges={F[Config].port: "last_wins"},
        )

        assert result.host == "first-host"
        assert result.port == 2000

    def test_append_lists(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"tags": ["a", "b"], "name": "test"}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"tags": ["c", "d"], "name": "override"}')

        @dataclass
        class Config:
            tags: list[str]
            name: str

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            field_merges={F[Config].tags: "append"},
        )

        assert result.tags == ["a", "b", "c", "d"]
        assert result.name == "override"

    def test_append_unique(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"tags": ["a", "b", "c"]}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"tags": ["b", "c", "d"]}')

        @dataclass
        class Config:
            tags: list[str]

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            field_merges={F[Config].tags: "append_unique"},
        )

        assert result.tags == ["a", "b", "c", "d"]

    def test_prepend(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"tags": ["a", "b"]}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"tags": ["c", "d"]}')

        @dataclass
        class Config:
            tags: list[str]

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            field_merges={F[Config].tags: "prepend"},
        )

        assert result.tags == ["c", "d", "a", "b"]

    def test_prepend_unique(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"tags": ["a", "b", "c"]}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"tags": ["b", "c", "d"]}')

        @dataclass
        class Config:
            tags: list[str]

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            field_merges={F[Config].tags: "prepend_unique"},
        )

        assert result.tags == ["b", "c", "d", "a"]

    def test_nested_field(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"database": {"host": "localhost", "port": 5432}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"database": {"host": "prod-host", "port": 3306}}')

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            field_merges={F[Config].database.host: "first_wins"},
        )

        assert result.database.host == "localhost"
        assert result.database.port == 3306

    def test_append_non_list_raises_type_error(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"value": "not-a-list"}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"value": "also-not"}')

        @dataclass
        class Config:
            value: str

        with pytest.raises(TypeError, match="APPEND strategy requires both values to be lists"):
            load(
                JsonSource(file=defaults),
                JsonSource(file=overrides),
                schema=Config,
                field_merges={F[Config].value: "append"},
            )

    def test_multiple_merge_rules(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "default-host", "port": 3000, "tags": ["a"]}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "override-host", "port": 9090, "tags": ["b"]}')

        @dataclass
        class Config:
            host: str
            port: int
            tags: list[str]

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            strategy="last_wins",
            field_merges={
                F[Config].host: "first_wins",
                F[Config].tags: "append",
            },
        )

        assert result.host == "default-host"
        assert result.port == 9090
        assert result.tags == ["a", "b"]

    def test_empty_field_merges_backward_compat(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            field_merges={},
        )

        assert result.host == "localhost"
        assert result.port == 8080


class TestFieldMergesDecorator:
    def test_decorator_with_field_merges(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "default-host", "port": 3000, "tags": ["a"]}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "override-host", "port": 9090, "tags": ["b"]}')

        @load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            field_merges={
                F["Config"].host: "first_wins",
                F["Config"].tags: "append",
            },
        )
        @dataclass
        class Config:
            host: str
            port: int
            tags: list[str]

        config = Config()
        assert config.host == "default-host"
        assert config.port == 9090
        assert config.tags == ["a", "b"]


class TestFieldMergesWithRaiseOnConflict:
    def test_field_merge_suppresses_conflict(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "host-a"}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "host-b", "port": 3000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            strategy="raise_on_conflict",
            field_merges={F[Config].host: "last_wins"},
        )

        assert result.host == "host-b"
        assert result.port == 3000

    def test_field_merge_first_wins_suppresses_conflict(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "host-a", "port": 3000}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "host-b"}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            strategy="raise_on_conflict",
            field_merges={F[Config].host: "first_wins"},
        )

        assert result.host == "host-a"
        assert result.port == 3000

    def test_unresolved_conflict_still_raises(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "host-a", "port": 3000}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "host-b", "port": 9090}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(MergeConflictError):
            load(
                JsonSource(file=a),
                JsonSource(file=b),
                schema=Config,
                strategy="raise_on_conflict",
                field_merges={F[Config].host: "last_wins"},
            )

    def test_nested_field_merge_suppresses_conflict(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"database": {"host": "host-a"}, "name": "app"}')

        b = tmp_path / "b.json"
        b.write_text('{"database": {"host": "host-b"}}')

        @dataclass
        class Database:
            host: str

        @dataclass
        class Config:
            database: Database
            name: str

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            strategy="raise_on_conflict",
            field_merges={F[Config].database.host: "last_wins"},
        )

        assert result.database.host == "host-b"
        assert result.name == "app"

    def test_all_conflicts_resolved_by_field_merges(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "host-a", "port": 3000}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "host-b", "port": 9090}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            strategy="raise_on_conflict",
            field_merges={
                F[Config].host: "first_wins",
                F[Config].port: max,
            },
        )

        assert result.host == "host-a"
        assert result.port == 9090


class TestFieldMergesErrors:
    @pytest.mark.parametrize(
        ("strategy", "match"),
        [
            pytest.param(
                "append",
                "APPEND strategy requires both values to be lists",
                id="append",
            ),
            pytest.param(
                "append_unique",
                "APPEND_UNIQUE strategy requires both values to be lists",
                id="append_unique",
            ),
            pytest.param(
                "prepend",
                "PREPEND strategy requires both values to be lists",
                id="prepend",
            ),
            pytest.param(
                "prepend_unique",
                "PREPEND_UNIQUE strategy requires both values to be lists",
                id="prepend_unique",
            ),
        ],
    )
    def test_list_strategy_on_strings_raises_type_error(
        self,
        tmp_path: Path,
        strategy: FieldMergeStrategyName,
        match: str,
    ):
        a = tmp_path / "a.json"
        a.write_text('{"value": "hello"}')

        b = tmp_path / "b.json"
        b.write_text('{"value": "world"}')

        @dataclass
        class Config:
            value: str

        with pytest.raises(TypeError, match=match):
            load(
                JsonSource(file=a),
                JsonSource(file=b),
                schema=Config,
                field_merges={F[Config].value: strategy},
            )

    @pytest.mark.parametrize(
        ("strategy", "match"),
        [
            pytest.param(
                "append",
                "APPEND strategy requires both values to be lists",
                id="append",
            ),
            pytest.param(
                "append_unique",
                "APPEND_UNIQUE strategy requires both values to be lists",
                id="append_unique",
            ),
            pytest.param(
                "prepend",
                "PREPEND strategy requires both values to be lists",
                id="prepend",
            ),
            pytest.param(
                "prepend_unique",
                "PREPEND_UNIQUE strategy requires both values to be lists",
                id="prepend_unique",
            ),
        ],
    )
    def test_list_strategy_on_integers_raises_type_error(
        self,
        tmp_path: Path,
        strategy: FieldMergeStrategyName,
        match: str,
    ):
        a = tmp_path / "a.json"
        a.write_text('{"value": 42}')

        b = tmp_path / "b.json"
        b.write_text('{"value": 99}')

        @dataclass
        class Config:
            value: int

        with pytest.raises(TypeError, match=match):
            load(
                JsonSource(file=a),
                JsonSource(file=b),
                schema=Config,
                field_merges={F[Config].value: strategy},
            )

    @pytest.mark.parametrize(
        ("strategy", "match"),
        [
            pytest.param(
                "append",
                "APPEND strategy requires both values to be lists, got list and str",
                id="append",
            ),
            pytest.param(
                "prepend",
                "PREPEND strategy requires both values to be lists, got list and str",
                id="prepend",
            ),
        ],
    )
    def test_list_strategy_mixed_types_raises_type_error(
        self,
        tmp_path: Path,
        strategy: FieldMergeStrategyName,
        match: str,
    ):
        a = tmp_path / "a.json"
        a.write_text('{"value": ["a", "b"]}')

        b = tmp_path / "b.json"
        b.write_text('{"value": "not-a-list"}')

        @dataclass
        class Config:
            value: list[str]

        with pytest.raises(TypeError, match=match):
            load(
                JsonSource(file=a),
                JsonSource(file=b),
                schema=Config,
                field_merges={F[Config].value: strategy},
            )

    @pytest.mark.parametrize(
        ("strategy", "expected"),
        [
            pytest.param(max, [3, 4], id="max"),
            pytest.param(min, [1, 2], id="min"),
        ],
    )
    def test_max_min_on_lists_compares_elementwise(
        self,
        tmp_path: Path,
        strategy: Callable[..., Any],
        expected: list[int],
    ):
        a = tmp_path / "a.json"
        a.write_text('{"value": [1, 2]}')

        b = tmp_path / "b.json"
        b.write_text('{"value": [3, 4]}')

        @dataclass
        class Config:
            value: list[int]

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            field_merges={F[Config].value: strategy},
        )

        assert result.value == expected

    @pytest.mark.parametrize(
        ("strategy", "match"),
        [
            pytest.param(max, "'>' not supported between instances of 'dict' and 'dict'", id="max"),
            pytest.param(min, "'<' not supported between instances of 'dict' and 'dict'", id="min"),
        ],
    )
    def test_max_min_on_dicts_raises_type_error(
        self,
        tmp_path: Path,
        strategy: Callable[..., Any],
        match: str,
    ):
        a = tmp_path / "a.json"
        a.write_text('{"value": {"nested": 1}}')

        b = tmp_path / "b.json"
        b.write_text('{"value": {"nested": 2}}')

        @dataclass
        class Config:
            value: dict[str, int]

        with pytest.raises(TypeError, match=match):
            load(
                JsonSource(file=a),
                JsonSource(file=b),
                schema=Config,
                field_merges={F[Config].value: strategy},
            )

    @pytest.mark.parametrize(
        ("strategy", "match"),
        [
            pytest.param(max, "'>' not supported between instances of 'int' and 'NoneType'", id="max"),
            pytest.param(min, "'<' not supported between instances of 'int' and 'NoneType'", id="min"),
        ],
    )
    def test_max_min_on_null_raises_type_error(
        self,
        tmp_path: Path,
        strategy: Callable[..., Any],
        match: str,
    ):
        a = tmp_path / "a.json"
        a.write_text('{"value": null}')

        b = tmp_path / "b.json"
        b.write_text('{"value": 10}')

        @dataclass
        class Config:
            value: int | None

        with pytest.raises(TypeError, match=match):
            load(
                JsonSource(file=a),
                JsonSource(file=b),
                schema=Config,
                field_merges={F[Config].value: strategy},
            )

    def test_field_merge_on_missing_key_in_one_source(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "localhost"}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "remote", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            field_merges={F[Config].host: "first_wins"},
        )

        assert result.host == "localhost"
        assert result.port == 8080

    def test_three_sources_field_merge(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"tags": ["a"]}')

        b = tmp_path / "b.json"
        b.write_text('{"tags": ["b"]}')

        c = tmp_path / "c.json"
        c.write_text('{"tags": ["c"]}')

        @dataclass
        class Config:
            tags: list[str]

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            JsonSource(file=c),
            schema=Config,
            field_merges={F[Config].tags: "append"},
        )

        assert result.tags == ["a", "b", "c"]

    def test_max_picks_larger_from_three_sources(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"priority": 5}')

        b = tmp_path / "b.json"
        b.write_text('{"priority": 15}')

        c = tmp_path / "c.json"
        c.write_text('{"priority": 10}')

        @dataclass
        class Config:
            priority: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            JsonSource(file=c),
            schema=Config,
            field_merges={F[Config].priority: max},
        )

        assert result.priority == 15

    def test_min_picks_smaller_from_three_sources(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"priority": 5}')

        b = tmp_path / "b.json"
        b.write_text('{"priority": 15}')

        c = tmp_path / "c.json"
        c.write_text('{"priority": 10}')

        @dataclass
        class Config:
            priority: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            JsonSource(file=c),
            schema=Config,
            field_merges={F[Config].priority: min},
        )

        assert result.priority == 5


class TestFieldMergesSameFieldNameNested:
    def test_first_wins_root_last_wins_nested(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"user_name": "root-first", "inner": {"user_name": "nested-first"}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"user_name": "root-second", "inner": {"user_name": "nested-second"}}')

        @dataclass
        class Inner:
            user_name: str

        @dataclass
        class Config:
            user_name: str
            inner: Inner

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            field_merges={
                F[Config].user_name: "first_wins",
                F[Config].inner.user_name: "last_wins",
            },
        )

        assert result.user_name == "root-first"
        assert result.inner.user_name == "nested-second"

    def test_last_wins_root_first_wins_nested(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"user_name": "root-first", "inner": {"user_name": "nested-first"}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"user_name": "root-second", "inner": {"user_name": "nested-second"}}')

        @dataclass
        class Inner:
            user_name: str

        @dataclass
        class Config:
            user_name: str
            inner: Inner

        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Config,
            field_merges={
                F[Config].user_name: "last_wins",
                F[Config].inner.user_name: "first_wins",
            },
        )

        assert result.user_name == "root-second"
        assert result.inner.user_name == "nested-first"


class TestCallableMergeStrategy:
    def test_callable_sum_two_sources(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"score": 10}')

        b = tmp_path / "b.json"
        b.write_text('{"score": 20}')

        @dataclass
        class Config:
            score: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            field_merges={F[Config].score: sum},
        )

        assert result.score == 30

    def test_callable_sum_three_sources(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"score": 5}')

        b = tmp_path / "b.json"
        b.write_text('{"score": 15}')

        c = tmp_path / "c.json"
        c.write_text('{"score": 10}')

        @dataclass
        class Config:
            score: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            JsonSource(file=c),
            schema=Config,
            field_merges={F[Config].score: sum},
        )

        assert result.score == 30

    def test_callable_average_three_sources(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"weight": 2}')

        b = tmp_path / "b.json"
        b.write_text('{"weight": 4}')

        c = tmp_path / "c.json"
        c.write_text('{"weight": 12}')

        @dataclass
        class Config:
            weight: float

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            JsonSource(file=c),
            schema=Config,
            field_merges={F[Config].weight: lambda vals: sum(vals) / len(vals)},
        )

        assert result.weight == 6.0

    def test_callable_max_builtin(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"priority": 5}')

        b = tmp_path / "b.json"
        b.write_text('{"priority": 15}')

        c = tmp_path / "c.json"
        c.write_text('{"priority": 10}')

        @dataclass
        class Config:
            priority: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            JsonSource(file=c),
            schema=Config,
            field_merges={F[Config].priority: max},
        )

        assert result.priority == 15

    def test_callable_with_nested_field(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"database": {"port": 3000}}')

        b = tmp_path / "b.json"
        b.write_text('{"database": {"port": 5000}}')

        c = tmp_path / "c.json"
        c.write_text('{"database": {"port": 7000}}')

        @dataclass
        class Database:
            port: int

        @dataclass
        class Config:
            database: Database

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            JsonSource(file=c),
            schema=Config,
            field_merges={F[Config].database.port: max},
        )

        assert result.database.port == 7000

    def test_callable_single_source(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"score": 42}')

        @dataclass
        class Config:
            score: int

        result = load(
            JsonSource(file=a),
            schema=Config,
            field_merges={F[Config].score: sum},
        )

        assert result.score == 42

    def test_single_source_merge_params_warning(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        a = tmp_path / "a.json"
        a.write_text('{"score": 42}')

        @dataclass
        class Config:
            score: int

        with caplog.at_level(logging.WARNING, logger="dature"):
            load(
                JsonSource(file=a),
                schema=Config,
                field_merges={F[Config].score: sum},
            )

        messages = [r.message for r in caplog.records if r.name == "dature"]
        assert messages == ["Merge-related parameters have no effect with a single source"]

    def test_callable_with_raise_on_conflict(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"score": 10, "name": "app"}')

        b = tmp_path / "b.json"
        b.write_text('{"score": 20}')

        @dataclass
        class Config:
            score: int
            name: str

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            strategy="raise_on_conflict",
            field_merges={F[Config].score: sum},
        )

        assert result.score == 30
        assert result.name == "app"

    def test_callable_mixed_with_enum_strategies(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "host-a", "score": 10, "tags": ["x"]}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "host-b", "score": 20, "tags": ["y"]}')

        @dataclass
        class Config:
            host: str
            score: int
            tags: list[str]

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=Config,
            field_merges={
                F[Config].host: "first_wins",
                F[Config].score: sum,
                F[Config].tags: "append",
            },
        )

        assert result.host == "host-a"
        assert result.score == 30
        assert result.tags == ["x", "y"]

    def test_callable_field_missing_in_some_sources(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"score": 10}')

        b = tmp_path / "b.json"
        b.write_text('{"name": "app"}')

        c = tmp_path / "c.json"
        c.write_text('{"score": 20}')

        @dataclass
        class Config:
            score: int
            name: str

        result = load(
            JsonSource(file=a),
            JsonSource(file=b),
            JsonSource(file=c),
            schema=Config,
            field_merges={F[Config].score: sum},
        )

        assert result.score == 30
        assert result.name == "app"
        assert result.name == "app"
        assert result.name == "app"
