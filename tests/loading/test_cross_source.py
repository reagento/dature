"""End-to-end tests for N-phase cross-source orchestration."""

import dataclasses
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import pytest

from dature import EnvSource, JsonSource, load
from dature.errors.exceptions import DatureError
from dature.loading.cross_source import (
    build_cross_ref_plan,
    evaluate_when_eager,
    evaluate_when_lazy,
    when_has_cross_refs,
)
from dature.sources.base import Source
from dature.sources.cli_base import CliSource
from dature.types import JSONValue


@dataclass(kw_only=True, repr=False)
class _Stub(Source):
    """Minimal in-memory source for orchestration tests.

    Exposes its own ``url`` and ``path`` init-fields in the loaded data so
    tests can observe the effect of cross-ref interpolation on them.
    """

    url: str | None = None
    path: str | None = None
    data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)

    format_name: ClassVar[str] = "stub"
    location_label: ClassVar[str] = "STUB"

    def _load(self) -> JSONValue:
        result = dict(self.data)
        if self.url is not None:
            result.setdefault("url", self.url)
        if self.path is not None:
            result.setdefault("path", self.path)
        return result


@dataclass(kw_only=True, repr=False)
class _BrokenDepStub(Source):
    """Source that always raises FileNotFoundError — used to simulate skipped deps."""

    format_name: ClassVar[str] = "broken_dep_stub"
    location_label: ClassVar[str] = "BROKEN_DEP"

    def _load(self) -> JSONValue:
        msg = "simulated missing source"
        raise FileNotFoundError(msg)


@dataclass
class _StrConfig:
    url: str = ""
    path: str = ""


_COLLISION_ERROR = (
    "Tag collision: multiple sources share resolved_tag='stub':\n"
    "  _Stub()\n"
    "  _Stub()\n"
    "Set an explicit tag= on at least one of them."
)

_UNKNOWN_TAG_SINGLE_ERROR = (
    "_Stub(tag='a') references unknown tag 'unknown'. "
    "Known tags: 'a'. "
    "Ensure a source with that tag is listed in the same load() call."
)

_UNKNOWN_TAG_TWO_SOURCES_ERROR = (
    "_Stub(tag='b') references unknown tag 'missing'. "
    "Known tags: 'a', 'b'. "
    "Ensure a source with that tag is listed in the same load() call."
)

_TWO_SOURCE_CYCLE_ERROR = (
    "Cross-source reference cycle detected:\n"
    "  _Stub(tag='a')  →  references ${@b.key}\n"
    "  _Stub(tag='b')  →  references ${@a.key}\n"
    "  closes back to _Stub(tag='a')\n"
    "\n"
    "Sources cannot reference each other's data in a cycle. "
    "Break the cycle by hardcoding one side or parsing one source imperatively."
)

_THREE_SOURCE_CYCLE_ERROR = (
    "Cross-source reference cycle detected:\n"
    "  _Stub(tag='a')  →  references ${@c.key}\n"
    "  _Stub(tag='c')  →  references ${@b.key}\n"
    "  _Stub(tag='b')  →  references ${@a.key}\n"
    "  closes back to _Stub(tag='a')\n"
    "\n"
    "Sources cannot reference each other's data in a cycle. "
    "Break the cycle by hardcoding one side or parsing one source imperatively."
)


class TestGraphValidation:
    """Tests for eager cross-ref graph validation via build_cross_ref_plan."""

    @pytest.mark.parametrize(
        "sources",
        [
            (_Stub(tag="a", data={"x": 1}), _Stub(tag="b", data={"y": 2})),
            (_Stub(data={"x": 1}), _Stub(data={"y": 2})),
            (_Stub(tag="a", data={}), _Stub(tag="b", data={})),
        ],
        ids=["tagged-no-refs", "untagged-no-refs", "explicit-tags"],
    )
    def test_returns_none(self, sources: tuple[_Stub, ...]) -> None:
        assert build_cross_ref_plan(sources) is None

    @pytest.mark.parametrize(
        ("sources", "expected_deps"),
        [
            (
                (_Stub(tag="a", data={"x": 1}), _Stub(tag="b", url="${@a.x}")),
                ((), (0,)),
            ),
            (
                (
                    _Stub(tag="a", data={"k": "v"}),
                    _Stub(tag="b", url="${@a.k}", data={"m": "2"}),
                    _Stub(tag="c", url="${@b.m}"),
                ),
                ((), (0,), (1,)),
            ),
            (
                (
                    _Stub(tag="a", data={"k": "v", "x": "1"}),
                    _Stub(tag="b", url="${@a.k}", data={"m": "2"}),
                    _Stub(tag="c", url="${@a.k}"),
                    _Stub(tag="d", url="${@b.m}"),
                ),
                ((), (0,), (0,), (1,)),
            ),
        ],
        ids=["two-sources", "linear-chain", "diamond"],
    )
    def test_plan_deps(
        self,
        sources: tuple[_Stub, ...],
        expected_deps: tuple[tuple[int, ...], ...],
    ) -> None:
        plan = build_cross_ref_plan(sources)
        assert plan is not None
        assert plan.deps == expected_deps

    @pytest.mark.parametrize(
        ("sources", "expected_error"),
        [
            (
                (_Stub(data={}), _Stub(data={}), _Stub(tag="c", url="${@stub.k}")),
                _COLLISION_ERROR,
            ),
            (
                (_Stub(tag="a", url="${@unknown.key}"),),
                _UNKNOWN_TAG_SINGLE_ERROR,
            ),
            (
                (_Stub(tag="a", data={}), _Stub(tag="b", url="${@missing.key}")),
                _UNKNOWN_TAG_TWO_SOURCES_ERROR,
            ),
            (
                (_Stub(tag="a", url="${@b.key}"), _Stub(tag="b", url="${@a.key}")),
                _TWO_SOURCE_CYCLE_ERROR,
            ),
            (
                (
                    _Stub(tag="a", url="${@c.key}"),
                    _Stub(tag="b", url="${@a.key}"),
                    _Stub(tag="c", url="${@b.key}"),
                ),
                _THREE_SOURCE_CYCLE_ERROR,
            ),
        ],
        ids=[
            "tag-collision",
            "unknown-tag-single",
            "unknown-tag-two-sources",
            "two-source-cycle",
            "three-source-cycle",
        ],
    )
    def test_error(self, sources: tuple[_Stub, ...], expected_error: str) -> None:
        with pytest.raises(DatureError) as exc_info:
            build_cross_ref_plan(sources)
        assert str(exc_info.value) == expected_error


class TestInterpolation:
    """Tests for lazy cross-ref interpolation during load()."""

    def test_single_ref_interpolated(self) -> None:
        env = _Stub(tag="env", data={"TOKEN": "secret"})
        vault = _Stub(tag="vault", url="${@env.TOKEN}", data={})

        result = load(env, vault, schema=_StrConfig)

        assert result.url == "secret"

    def test_no_ref_source_not_affected(self) -> None:
        a = _Stub(tag="a", data={"url": "original", "path": "p"})

        result = load(a, schema=_StrConfig)

        assert result.url == "original"

    def test_linear_chain_init_fields_resolved(self) -> None:
        env = _Stub(tag="env", data={"TOKEN": "mytoken"})
        # vault's url gets "mytoken"; vault's data has "host"
        vault = _Stub(tag="vault", url="${@env.TOKEN}", data={"url": "vault.local"})
        # app gets vault.local from vault's loaded data
        app = _Stub(tag="app", url="${@vault.url}", data={})

        result = load(env, vault, app, schema=_StrConfig)

        assert result.url == "vault.local"

    def test_ref_with_default_used_when_missing(self) -> None:
        a = _Stub(tag="a", data={"url": "fallback"})
        b = _Stub(tag="b", url="${@a.missing:-fallback}")

        result = load(a, b, schema=_StrConfig)

        assert result.url == "fallback"

    def test_multiple_fields_interpolated(self) -> None:
        env = _Stub(tag="env", data={"url": "db.example.com", "path": "5432"})
        app = _Stub(tag="app", url="${@env.url}", path="${@env.path}", data={})

        result = load(env, app, schema=_StrConfig)

        assert result.url == "db.example.com"
        assert result.path == "5432"

    def test_double_dollar_escaping_in_field(self) -> None:
        a = _Stub(tag="a", data={"url": "v"})
        # $${@a.url} → literal "${@a.url}" (not interpolated)
        b = _Stub(tag="b", url="$${@a.url}", data={"url": "${@a.url}"})

        result = load(a, b, schema=_StrConfig)

        assert result.url == "${@a.url}"

    def test_skipped_dep_contributes_empty_context_for_default_fallback(self) -> None:
        # Regression: when a dependency source is skipped (skip_if_broken=True and
        # the file doesn't exist), _resolve_dep_refs writes context[dep_tag] = {} so
        # that ${@dep.key:-fallback} default expressions still resolve, rather than
        # raising "unknown tag".
        broken = _BrokenDepStub(tag="dep", skip_if_broken=True)
        consumer = _Stub(tag="consumer", url="${@dep.key:-used-fallback}", data={})

        result = load(broken, consumer, schema=_StrConfig, skip_broken_sources=True)

        assert result.url == "used-fallback"


class TestSingleSourceEscaping:
    def test_double_dollar_in_file_path_resolved_single_source(self) -> None:
        # Regression: single-source load() must apply $$ → $ expansion so that
        # escaped refs in init-fields become literal characters.
        @dataclass
        class Config:
            value: str = ""

        tmpdir = Path(tempfile.mkdtemp())
        config_file = tmpdir / "${@env.something}"
        config_file.write_text('{"value": "ok"}')
        try:
            result = load(
                JsonSource(file=str(tmpdir / "$${@env.something}")),
                schema=Config,
            )
            assert result.value == "ok"
        finally:
            config_file.unlink()
            tmpdir.rmdir()


# ---------------------------------------------------------------------------
# Integration tests with real sources (EnvSource, JsonSource, CliSource)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class _DictCliSource(CliSource):
    """CliSource stub that serves a fixed flat dict instead of sys.argv.

    Uses ``nested_sep="--"`` (CliSource default): ``{"db--host": "v"}``
    unfolds to ``{"db": {"host": "v"}}``, so ``${@cli.db.host}`` resolves.
    """

    format_name: ClassVar[str] = "cli"
    data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)

    def _parse_argv(self) -> dict[str, JSONValue]:
        return self.data


@dataclass
class _Config:
    value: str = ""


class TestEnvSourceProvidesFilePath:
    """EnvSource → JsonSource(file=...): env var holds the config file path.

    EnvSource key semantics in cross-refs:
      EnvSource(prefix="APP_"): APP_HOST → key "host"    (prefix stripped, lowercased)
      EnvSource()             : APP_HOST → key "app_host" (no stripping, lowercased)
    """

    def test_prefixed_env_var_as_file_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "app.json"
        config_file.write_text('{"value": "from-file"}')
        monkeypatch.setenv("APP_CONFIG_PATH", str(config_file))

        result = load(
            JsonSource(file="${@env.config_path}"),
            EnvSource(prefix="APP_"),
            schema=_Config,
        )

        assert result.value == "from-file"

    def test_unprefixed_env_var_as_file_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "app.json"
        config_file.write_text('{"value": "no-prefix"}')
        monkeypatch.setenv("CONFIG_PATH", str(config_file))

        result = load(
            JsonSource(file="${@env.config_path}"),
            EnvSource(),
            schema=_Config,
        )

        assert result.value == "no-prefix"

    def test_source_order_does_not_matter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "app.json"
        config_file.write_text('{"value": "resolved"}')
        monkeypatch.setenv("CFG_PATH", str(config_file))

        # JsonSource listed first, but EnvSource is loaded first (cross-ref dep)
        result = load(
            JsonSource(file="${@env.cfg_path}"),
            EnvSource(),
            schema=_Config,
        )

        assert result.value == "resolved"


class TestEnvSourceProvidesPrefix:
    """EnvSource → EnvSource(prefix=...): one env source configures the prefix of another."""

    def test_prefix_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # "meta" source has no prefix → APP_PREFIX → key "app_prefix" (lowercased)
        monkeypatch.setenv("APP_PREFIX", "MYAPP_")
        # "app" source reads prefix from "meta", then loads MYAPP_VALUE → key "value"
        monkeypatch.setenv("MYAPP_VALUE", "hello")

        result = load(
            EnvSource(prefix="${@meta.app_prefix}", tag="app"),
            EnvSource(tag="meta"),
            schema=_Config,
        )

        assert result.value == "hello"


class TestCliSourceProvidesFilePath:
    """CliSource → JsonSource(file=...): CLI argument holds the config file path."""

    def test_flat_cli_arg_as_file_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "app.json"
        config_file.write_text('{"value": "from-cli-path"}')

        result = load(
            JsonSource(file="${@cli.config_path}"),
            _DictCliSource(data={"config_path": str(config_file)}),
            schema=_Config,
        )

        assert result.value == "from-cli-path"

    def test_nested_cli_arg_as_file_path(self, tmp_path: Path) -> None:
        """--db--config_path on the CLI unfolds to db.config_path for ${@cli.db.config_path}."""
        config_file = tmp_path / "db.json"
        config_file.write_text('{"value": "db-config"}')

        result = load(
            JsonSource(file="${@cli.db.config_path}"),
            _DictCliSource(data={"db--config_path": str(config_file)}),
            schema=_Config,
        )

        assert result.value == "db-config"


class TestCliSourceProvidesEnvPrefix:
    """CliSource → EnvSource(prefix=...): CLI arg configures which env namespace to read."""

    def test_env_prefix_from_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROD_VALUE", "prod-secret")

        result = load(
            EnvSource(prefix="${@cli.env_prefix}", tag="app"),
            _DictCliSource(data={"env_prefix": "PROD_"}),
            schema=_Config,
        )

        assert result.value == "prod-secret"


class TestThreeSourceChain:
    """Linear A → B → C dependency chain across different source types."""

    def test_cli_sets_env_prefix_env_provides_file_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "app.json"
        config_file.write_text('{"value": "end-of-chain"}')
        monkeypatch.setenv("APP_CONFIG_PATH", str(config_file))

        result = load(
            JsonSource(file="${@app.config_path}"),
            EnvSource(prefix="${@cli.env_prefix}", tag="app"),
            _DictCliSource(data={"env_prefix": "APP_"}),
            schema=_Config,
        )

        assert result.value == "end-of-chain"

    def test_two_json_sources_one_provides_path_for_other(self, tmp_path: Path) -> None:
        data_file = tmp_path / "data.json"
        data_file.write_text('{"value": "nested-json"}')

        ptr_file = tmp_path / "ptr.json"
        ptr_file.write_text(json.dumps({"data_path": str(data_file)}))

        result = load(
            JsonSource(file="${@ptr.data_path}", tag="data"),
            JsonSource(file=ptr_file, tag="ptr"),
            schema=_Config,
        )

        assert result.value == "nested-json"


class TestWhenHasCrossRefs:
    @pytest.mark.parametrize(
        ("when", "expected"),
        [
            (None, False),
            ({}, False),
            ({"${APP_ENV}": "prod"}, False),
            ({"${@env.mode}": "prod"}, True),
            ({"${APP_ENV}": "prod", "${@env.mode}": "staging"}, True),
        ],
        ids=["none", "empty", "env-only", "cross-ref", "mixed"],
    )
    def test_when_has_cross_refs(self, when: "dict[str, str] | None", expected: bool) -> None:
        @dataclass(kw_only=True, repr=False)
        class _S(Source):
            format_name = "s"
            location_label = "S"

            def _load(self) -> JSONValue:
                return {}

        source = _S(when=when)
        assert when_has_cross_refs(source) is expected


class TestEvaluateWhenEager:
    def test_none_when_returns_true(self) -> None:
        assert evaluate_when_eager(None) is True

    def test_empty_when_returns_true(self) -> None:
        assert evaluate_when_eager({}) is True

    def test_env_var_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        assert evaluate_when_eager({"${APP_ENV}": "prod"}) is True

    def test_env_var_no_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "dev")
        assert evaluate_when_eager({"${APP_ENV}": "prod"}) is False

    def test_tuple_expected_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "staging")
        assert evaluate_when_eager({"${APP_ENV}": ("prod", "staging")}) is True

    def test_tuple_expected_no_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "dev")
        assert evaluate_when_eager({"${APP_ENV}": ("prod", "staging")}) is False

    def test_cross_ref_key_is_not_expanded(self) -> None:
        assert evaluate_when_eager({"${@env.mode}": "prod"}) is False

    def test_multiple_conditions_all_must_pass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("APP_REGION", "us")
        assert evaluate_when_eager({"${APP_ENV}": "prod", "${APP_REGION}": "us"}) is True
        assert evaluate_when_eager({"${APP_ENV}": "prod", "${APP_REGION}": "eu"}) is False

    def test_unset_env_var_literal_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UNSET_VAR", raising=False)
        assert evaluate_when_eager({"${UNSET_VAR}": "${UNSET_VAR}"}) is True


class TestEvaluateWhenLazy:
    def test_none_when_returns_true(self) -> None:
        assert evaluate_when_lazy(None, {}) is True

    def test_env_var_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        assert evaluate_when_lazy({"${APP_ENV}": "prod"}, {}) is True

    def test_cross_ref_match(self) -> None:
        context = {"env": {"mode": "prod"}}
        assert evaluate_when_lazy({"${@env.mode}": "prod"}, context) is True

    def test_cross_ref_no_match(self) -> None:
        context = {"env": {"mode": "dev"}}
        assert evaluate_when_lazy({"${@env.mode}": "prod"}, context) is False
