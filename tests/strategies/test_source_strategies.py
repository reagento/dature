"""Tests for source-level merge strategies and the public Protocol contract."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from dature import EnvSource, JsonSource, load
from dature.field_path import F
from dature.strategies.source import (
    LoadCtx,
    SourceFirstFound,
    SourceFirstWins,
    SourceLastWins,
    SourceMergeStrategy,
)

if TYPE_CHECKING:
    from dature.types import JSONValue


@dataclass
class Config:
    host: str
    port: int


class TestStrategyInstancesViaPublicAPI:
    """Built-in strategies can be passed as instances to ``load()``."""

    @pytest.mark.parametrize(
        "strategy",
        [
            pytest.param(SourceLastWins(), id="last_wins"),
            pytest.param(SourceFirstWins(), id="first_wins"),
            pytest.param(SourceFirstFound(), id="first_found"),
        ],
    )
    def test_built_in_instance(self, tmp_path: Path, strategy: SourceMergeStrategy):
        a = tmp_path / "a.json"
        a.write_text('{"host": "localhost", "port": 3000}')

        result = load(JsonSource(file=a), schema=Config, strategy=strategy)
        assert result.host == "localhost"
        assert result.port == 3000

    def test_string_and_instance_equivalent_for_last_wins(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "h1", "port": 1}')
        b = tmp_path / "b.json"
        b.write_text('{"host": "h2", "port": 2}')

        from_string = load(JsonSource(file=a), JsonSource(file=b), schema=Config, strategy="last_wins")
        from_instance = load(JsonSource(file=a), JsonSource(file=b), schema=Config, strategy=SourceLastWins())
        assert from_string == from_instance


class TestCustomStrategy:
    def test_callable_class_satisfies_protocol(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "from-a", "port": 1}')
        b = tmp_path / "b.json"
        b.write_text('{"host": "from-b", "port": 2}')

        class TakeFirstNonEmpty:
            def __call__(self, sources, ctx: LoadCtx):
                for src in sources:
                    data = ctx.load(src)
                    if data:
                        return data
                return {}

        # isinstance check against Protocol works (runtime_checkable).
        custom: SourceMergeStrategy = TakeFirstNonEmpty()
        assert isinstance(custom, SourceMergeStrategy)

        result = load(JsonSource(file=a), JsonSource(file=b), schema=Config, strategy=custom)
        assert result.host == "from-a"

    def test_custom_can_compose_built_in(self, tmp_path: Path, monkeypatch):
        """Custom strategy composes :class:`SourceLastWins` for non-env sources."""
        monkeypatch.setenv("APP_HOST", "from-env")

        a = tmp_path / "a.json"
        a.write_text('{"host": "from-file", "port": 9000}')

        class EnvOverrides:
            """The files are merged last_wins; the env source is superimposed strictly on top."""

            def __call__(self, sources, ctx: LoadCtx):
                files = [s for s in sources if not isinstance(s, EnvSource)]
                envs = [s for s in sources if isinstance(s, EnvSource)]
                base = SourceLastWins()(files, ctx)
                for env_src in envs:
                    data = ctx.load(env_src)
                    if isinstance(base, dict) and isinstance(data, dict):
                        base = {**base, **data}
                return base

        result = load(
            JsonSource(file=a),
            EnvSource(prefix="APP_"),
            schema=Config,
            strategy=EnvOverrides(),
        )
        assert result.host == "from-env"
        assert result.port == 9000


class TestFirstFoundShortCircuit:
    def test_skips_subsequent_sources_after_success(self, tmp_path: Path):
        good = tmp_path / "good.json"
        good.write_text('{"host": "loaded", "port": 1}')
        bad = tmp_path / "bad.json"  # would raise if loaded — file does not exist

        result = load(
            JsonSource(file=good),
            JsonSource(file=bad),
            schema=Config,
            strategy="first_found",
        )
        assert result.host == "loaded"

    def test_silently_skips_broken_then_returns_first_good(self, tmp_path: Path):
        missing = tmp_path / "missing.json"  # does not exist — broken
        good = tmp_path / "good.json"
        good.write_text('{"host": "ok", "port": 7}')

        result = load(
            JsonSource(file=missing),
            JsonSource(file=good),
            schema=Config,
            strategy="first_found",
        )
        assert result.host == "ok"
        assert result.port == 7


class TestLoadCtxPublicAPI:
    """Strategies can read ``ctx.dataclass_name`` and ``ctx.field_merge_paths``."""

    def test_strategy_reads_dataclass_name_and_field_merge_paths(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "h1", "port": 1, "tags": ["x"]}')
        b = tmp_path / "b.json"
        b.write_text('{"host": "h2", "port": 2, "tags": ["y"]}')

        seen: dict[str, object] = {}

        class CapturingStrategy:
            def __call__(self, sources, ctx: LoadCtx):
                seen["dataclass_name"] = ctx.dataclass_name
                seen["field_merge_paths"] = ctx.field_merge_paths
                base: JSONValue = {}
                for src in sources:
                    base = ctx.merge(source=src, base=base)
                return base

        @dataclass
        class WithTags:
            host: str
            port: int
            tags: list[str]

        load(
            JsonSource(file=a),
            JsonSource(file=b),
            schema=WithTags,
            strategy=CapturingStrategy(),
            field_merges={F[WithTags].tags: "append"},
        )

        assert seen["dataclass_name"] == "WithTags"
        assert seen["field_merge_paths"] == frozenset({"tags"})
