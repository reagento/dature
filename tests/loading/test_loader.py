"""Unit tests for src/dature/loading/loader.py — the public ``Loader`` class."""

import dataclasses
from dataclasses import dataclass
from datetime import timedelta
from enum import Flag
from io import BytesIO, StringIO
from pathlib import Path
from typing import Annotated, ClassVar
from unittest.mock import patch

import pytest
import time_machine

import dature
import dature.sources.base
from dature import EnvFileSource, EnvSource, JsonSource, Loader, V, When, load
from dature.errors.exceptions import CrossRefExpandError, DatureConfigError, DatureError
from dature.sources.base import Source
from dature.type_aliases import JSONValue


@dataclass
class _Config:
    host: str
    port: int


@dataclass(kw_only=True, repr=False)
class _Stub(dature.sources.base.Source):
    """Minimal in-memory source for when= tests."""

    data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)

    format_name: ClassVar[str] = "stub"
    location_label: ClassVar[str] = "STUB"

    def _load(self) -> JSONValue:
        return dict(self.data)


@dataclass(kw_only=True, repr=False)
class _StubUrl(dature.sources.base.Source):
    """In-memory source that returns a single url key — used for cross-ref tests."""

    url: str = ""
    format_name: ClassVar[str] = "stuburl"
    location_label: ClassVar[str] = "STUB"

    def _load(self) -> JSONValue:
        return {"url": self.url}


@dataclass
class _WhenCfg:
    x: str = ""


class TestLoaderValidation:
    def test_no_sources_raises(self) -> None:
        with pytest.raises(TypeError, match="at least one Source"):
            Loader(schema=_Config)

    def test_non_source_argument_raises(self) -> None:
        with pytest.raises(TypeError, match="must be SourceProtocol instances"):
            Loader("not a source", schema=_Config)

    def test_negative_timedelta_raises(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "x", "port": 1}')
        with pytest.raises(ValueError, match="cache timedelta must be non-negative"):
            Loader(JsonSource(file=json_file), schema=_Config, cache=timedelta(seconds=-1))


class TestLoaderLoad:
    def test_returns_loaded_dataclass(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 3000}')

        result = Loader(JsonSource(file=json_file), schema=_Config).load()

        assert result.host == "h"
        assert result.port == 3000

    def test_with_prefix(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"app": {"host": "nested", "port": 1}}')

        @dataclass
        class Config:
            host: str
            port: int

        result = Loader(JsonSource(file=json_file, prefix="app"), schema=Config).load()

        assert result.host == "nested"
        assert result.port == 1


class TestLoaderCache:
    def test_cache_true_repeats_same_instance(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=True)

        first = loader.load()
        second = loader.load()

        assert first is second

    def test_cache_false_reloads_every_call(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=False)

        first = loader.load()
        second = loader.load()

        assert first is not second

    @pytest.mark.parametrize(
        ("cache_arg", "advance_seconds", "expected_second"),
        [
            (True, 0.0, "original"),
            (False, 0.0, "updated"),
            (timedelta(seconds=30), 10.0, "original"),
            (timedelta(seconds=30), 31.0, "updated"),
            (timedelta(0), 0.0, "updated"),
        ],
        ids=["true", "false", "ttl-hit", "ttl-expired", "ttl-zero"],
    )
    def test_loader_cache_matrix(
        self,
        tmp_path: Path,
        time_control: time_machine.Traveller,
        cache_arg: bool | timedelta,
        advance_seconds: float,
        expected_second: str,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "original", "port": 8080}')
        source = JsonSource(file=json_file)

        @dataclass
        class Config:
            host: str
            port: int

        loader = Loader(source, schema=Config, cache=cache_arg)
        first = loader.load()
        json_file.write_text('{"host": "updated", "port": 9090}')
        time_control.shift(advance_seconds)
        second = loader.load()

        assert first.host == "original"
        assert second.host == expected_second

    def test_when_routing_re_evaluated_after_env_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # when= is re-evaluated on every .load() call. When the enabled set changes,
        # the cache is automatically cleared and a fresh load runs.
        monkeypatch.setenv("APP_ENV", "dev")
        loader = Loader(
            _Stub(data={"x": "prod"}, when=When("${APP_ENV}") == "prod"),
            _Stub(data={"x": "dev"}, when=When("${APP_ENV}") == "dev"),
            schema=_WhenCfg,
            cache=True,
        )
        first = loader.load()
        assert first.x == "dev"

        monkeypatch.setenv("APP_ENV", "prod")
        second = loader.load()
        # when= routing changed → cache cleared automatically → fresh load.
        assert second.x == "prod"
        assert first is not second

    def test_loader_per_schema_independent(self, tmp_path: Path) -> None:
        a_file = tmp_path / "a.json"
        a_file.write_text('{"name": "A"}')
        source = JsonSource(file=a_file)

        @dataclass
        class ConfigA:
            name: str

        @dataclass
        class ConfigB:
            name: str

        first_a = Loader(source, schema=ConfigA, cache=True).load()
        first_b = Loader(source, schema=ConfigB, cache=True).load()

        assert first_a.name == "A"
        assert first_b.name == "A"
        assert type(first_a).__name__ == "ConfigA"
        assert type(first_b).__name__ == "ConfigB"

    def test_loader_different_sources_independent(self, tmp_path: Path) -> None:
        a_file = tmp_path / "a.json"
        a_file.write_text('{"name": "A"}')
        b_file = tmp_path / "b.json"
        b_file.write_text('{"name": "B"}')

        source_a = JsonSource(file=a_file)
        source_b = JsonSource(file=b_file)

        @dataclass
        class Config:
            name: str

        cfg_a = Loader(source_a, schema=Config, cache=True).load()
        cfg_b = Loader(source_b, schema=Config, cache=True).load()

        assert cfg_a.name == "A"
        assert cfg_b.name == "B"


class TestLoaderMulti:
    def test_two_sources_merge(self, tmp_path: Path) -> None:
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')
        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        loader = Loader(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=_Config,
            cache=True,
        )
        cfg = loader.load()

        assert cfg.host == "localhost"
        assert cfg.port == 8080

    def test_multi_cache_hits_within_loader(self, tmp_path: Path) -> None:
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')
        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"port": 8080}')

        loader = Loader(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=_Config,
            cache=True,
        )
        first = loader.load()
        defaults.write_text('{"host": "changed", "port": 3000}')
        second = loader.load()

        assert first is second


class TestLoaderAsDecorator:
    def test_not_dataclass_raises(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        decorator = Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)

        with pytest.raises(TypeError, match="must be a dataclass"):

            @decorator
            class NotADataclass:  # type: ignore[type-var]
                pass

    def test_does_not_patch_original_class(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        @dataclass
        class Config:
            name: str

        original_init = Config.__init__
        original_post_init = getattr(Config, "__post_init__", None)
        Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        assert Config.__init__ is original_init
        assert getattr(Config, "__post_init__", None) is original_post_init

    def test_loads_on_init(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "from_file", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        Config = Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)  # type: ignore[misc]  # noqa: N806

        config = Config()
        assert config.name == "from_file"
        assert config.port == 8080

    def test_init_args_override_loaded(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "from_file", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        Config = Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)  # type: ignore[misc]  # noqa: N806

        config = Config(name="overridden")
        assert config.name == "overridden"
        assert config.port == 8080

    def test_returns_subclass_of_original(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        @dataclass
        class Config:
            name: str

        original = Config
        result = Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)

        assert result is not original
        assert issubclass(result, original)
        assert result.__name__ == original.__name__

    def test_preserves_original_post_init(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test"}')

        post_init_called: list[bool] = []

        @dataclass
        class Config:
            name: str

            def __post_init__(self) -> None:
                post_init_called.append(True)

        Config = Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)  # type: ignore[misc]  # noqa: N806

        Config()
        assert len(post_init_called) == 1


class TestLoaderAsDecoratorCache:
    @pytest.mark.parametrize(
        ("cache_arg", "first_name", "second_name_expected"),
        [
            (True, "original", "original"),
            (False, "original", "updated"),
        ],
        ids=["cache_true", "cache_false"],
    )
    def test_cache_behavior(
        self,
        tmp_path: Path,
        cache_arg: bool,
        first_name: str,
        second_name_expected: str,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        Config = Loader.as_decorator(JsonSource(file=json_file), cache=cache_arg, debug=False)(Config)  # type: ignore[misc]  # noqa: N806

        first = Config()
        json_file.write_text('{"name": "updated", "port": 9090}')
        second = Config()

        assert first.name == first_name
        assert second.name == second_name_expected

    def test_cache_allows_override(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "original", "port": 8080}')

        @dataclass
        class Config:
            name: str
            port: int

        Config = Loader.as_decorator(JsonSource(file=json_file), cache=True, debug=False)(Config)  # type: ignore[misc]  # noqa: N806

        first = Config()
        assert first.name == "original"
        assert first.port == 8080

        second = Config(name="overridden")
        assert second.name == "overridden"
        assert second.port == 8080


class _Permission(Flag):
    READ = 1
    WRITE = 2
    EXECUTE = 4


class TestLoaderFlagFields:
    @pytest.mark.parametrize(
        ("source_type", "perms_value", "expected", "mode"),
        [
            ("env_file", "3", _Permission.READ | _Permission.WRITE, "function"),
            ("json", 3, _Permission.READ | _Permission.WRITE, "function"),
            ("env_file", "5", _Permission.READ | _Permission.EXECUTE, "decorator"),
            ("json", 7, _Permission.READ | _Permission.WRITE | _Permission.EXECUTE, "decorator"),
        ],
        ids=["fn-env-file", "fn-json", "dec-env-file", "dec-json"],
    )
    def test_flag_coercion(
        self,
        tmp_path: Path,
        source_type: str,
        perms_value: object,
        expected: _Permission,
        mode: str,
    ) -> None:
        @dataclass
        class Config:
            name: str
            perms: _Permission

        source: Source
        if source_type == "env_file":
            env_file = tmp_path / "config.env"
            env_file.write_text(f"NAME=test\nPERMS={perms_value}\n")
            source = EnvFileSource(file=env_file)
        else:
            json_file = tmp_path / "config.json"
            json_file.write_text(f'{{"name": "test", "perms": {perms_value}}}')
            source = JsonSource(file=json_file)

        if mode == "function":
            assert Loader(source, schema=Config, debug=False).load().perms == expected
        else:
            Config = Loader.as_decorator(source, cache=True, debug=False)(Config)  # type: ignore[misc]  # noqa: N806
            assert Config().perms == expected


class TestLoaderFilelikeSources:
    @pytest.mark.parametrize(
        "stream",
        [
            BytesIO(b'{"name": "test", "port": 3000}'),
            StringIO('{"name": "test", "port": 3000}'),
        ],
        ids=["bytes-io", "string-io"],
    )
    def test_json_from_filelike(self, stream: BytesIO | StringIO) -> None:
        @dataclass
        class Config:
            name: str
            port: int

        result = Loader(JsonSource(file=stream), schema=Config, debug=False).load()
        assert result.name == "test"
        assert result.port == 3000


class TestRetortCacheNoCollision:
    """Regression: two sources of the same type with different per-source config
    must each use their own retort, not share the first source's."""

    def test_root_validator_fires_on_final_config(self) -> None:
        """root_validators= on Loader fires once on the final merged config."""

        @dataclass
        class Config:
            value: str

        source_a = _Stub(data={"value": "bad"})
        source_b = _Stub(data={"value": "bad"})

        with pytest.raises(DatureConfigError):
            Loader(
                source_a,
                source_b,
                schema=Config,
                debug=False,
                root_validators=(V.root(lambda cfg: cfg.value != "bad", error_message="value must not be 'bad'"),),
            ).load()

    def test_path_object_directly(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "direct_path"}')

        @dataclass
        class Config:
            name: str

        result = Loader(JsonSource(file=json_file), schema=Config, debug=False).load()
        assert result.name == "direct_path"


# ---------------------------------------------------------------------------
# when= conditional source inclusion
# ---------------------------------------------------------------------------


class TestEagerWhen:
    @pytest.mark.parametrize(
        ("env_value", "expected_x"),
        [
            ("prod", "prod_val"),
            ("dev", "dev_val"),
        ],
    )
    def test_single_env_var_mutual_exclusive(self, monkeypatch, env_value, expected_x):
        """Mutually exclusive when= → exactly one source active."""
        monkeypatch.setenv("APP_ENV", env_value)
        result = load(
            _Stub(data={"x": "prod_val"}, when=When("${APP_ENV}") == "prod"),
            _Stub(data={"x": "dev_val"}, when=When("${APP_ENV}") == "dev"),
            schema=_WhenCfg,
        )
        assert result.x == expected_x

    @pytest.mark.parametrize(
        ("env_value", "expected_x"),
        [
            ("prod", "override"),  # conditional source is last → last_wins
            ("dev", "default"),  # conditional disabled → only default active
            (None, "default"),
        ],
    )
    def test_conditional_overrides_default_when_active(self, monkeypatch, env_value, expected_x):
        """Conditional source placed last overrides the default when enabled."""
        if env_value is None:
            monkeypatch.delenv("APP_ENV", raising=False)
        else:
            monkeypatch.setenv("APP_ENV", env_value)

        result = load(
            _Stub(data={"x": "default"}),
            _Stub(data={"x": "override"}, when=When("${APP_ENV}") == "prod"),
            schema=_WhenCfg,
        )
        assert result.x == expected_x

    @pytest.mark.parametrize(
        ("env_value", "expected_x"),
        [
            (None, "prod_val"),  # ${APP_ENV:-prod} → "prod" → enabled
            ("prod", "prod_val"),
            ("dev", "dev_val"),
        ],
    )
    def test_env_var_with_default(self, monkeypatch, env_value, expected_x):
        if env_value is None:
            monkeypatch.delenv("APP_ENV", raising=False)
        else:
            monkeypatch.setenv("APP_ENV", env_value)

        result = load(
            _Stub(data={"x": "prod_val"}, when=When("${APP_ENV:-prod}") == "prod"),
            _Stub(data={"x": "dev_val"}, when=When("${APP_ENV:-prod}") == "dev"),
            schema=_WhenCfg,
        )
        assert result.x == expected_x

    @pytest.mark.parametrize(
        ("env_value", "expected_x"),
        [
            ("dev", "from_stub"),
            ("local", "from_stub"),
            ("prod", "fallback"),
            (None, "fallback"),
        ],
    )
    def test_tuple_of_expected_values(self, monkeypatch, env_value, expected_x):
        if env_value is None:
            monkeypatch.delenv("APP_ENV", raising=False)
        else:
            monkeypatch.setenv("APP_ENV", env_value)

        result = load(
            _Stub(data={"x": "fallback"}),
            _Stub(data={"x": "from_stub"}, when=When("${APP_ENV}").in_("dev", "local")),
            schema=_WhenCfg,
        )
        assert result.x == expected_x

    @pytest.mark.parametrize(
        ("a", "b", "expected_x"),
        [
            ("1", "2", "from_stub"),
            ("1", "x", "fallback"),
            ("x", "2", "fallback"),
            (None, None, "fallback"),
        ],
    )
    def test_multiple_keys_and(self, monkeypatch, a, b, expected_x):
        """All keys must match (AND semantics)."""
        if a is None:
            monkeypatch.delenv("A", raising=False)
        else:
            monkeypatch.setenv("A", a)
        if b is None:
            monkeypatch.delenv("B", raising=False)
        else:
            monkeypatch.setenv("B", b)

        result = load(
            _Stub(data={"x": "fallback"}),
            _Stub(data={"x": "from_stub"}, when=(When("${A}") == "1") & (When("${B}") == "2")),
            schema=_WhenCfg,
        )
        assert result.x == expected_x

    def test_none_always_enabled(self):
        result = load(
            _Stub(data={"x": "ok"}, when=None),
            schema=_WhenCfg,
        )
        assert result.x == "ok"

    def test_load_raw_not_called_when_disabled(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev")
        load_calls: list[str] = []

        @dataclass(kw_only=True, repr=False)
        class _Tracked(dature.sources.base.Source):
            name: str = ""
            data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)
            format_name: ClassVar[str] = "tracked"
            location_label: ClassVar[str] = "STUB"

            def _load(self) -> JSONValue:
                load_calls.append(self.name)
                return dict(self.data)

        result = load(
            _Tracked(name="disabled", data={"x": "secret"}, when=When("${APP_ENV}") == "prod"),
            _Tracked(name="active", data={"x": "ok"}),
            schema=_WhenCfg,
        )
        assert "disabled" not in load_calls
        assert "active" in load_calls
        assert result.x == "ok"

    def test_all_sources_disabled_raises(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev")
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                _Stub(data={"x": "a"}, when=When("${APP_ENV}") == "prod"),
                schema=_WhenCfg,
            )
        assert str(exc_info.value.exceptions[0]) == (
            "Loader requires at least one enabled Source (all sources filtered out by when=)"
        )

    def test_single_source_mode_when_one_passes_eager(self, monkeypatch):
        """Single enabled source after eager filter → _do_load_single path."""
        monkeypatch.setenv("APP_ENV", "prod")
        result = load(
            _Stub(data={"x": "prod_val"}, when=When("${APP_ENV}") == "prod"),
            schema=_WhenCfg,
        )
        assert result.x == "prod_val"


class TestLazyWhen:
    def test_when_resolved_from_cross_source(self):
        """when= key with ${@tag.key} is evaluated after the dep source loads."""
        # EnvSource lowercases keys: APP_ENV → app_env in loaded data
        with patch.dict("os.environ", {"APP_ENV": "prod"}, clear=False):
            result = load(
                EnvSource(tag="env"),
                _Stub(data={"x": "conditional"}, when=When("${@env.app_env}") == "prod"),
                _Stub(data={"x": "fallback"}, when=When("${@env.app_env}") == "dev"),
                schema=_WhenCfg,
            )
        assert result.x == "conditional"

    def test_when_lazy_disabled_cross_ref_gets_empty_context(self):
        """Disabled lazy source: downstream ${@tag.key} without default → error."""

        @dataclass
        class _Cfg2:
            url: str = ""

        with patch.dict("os.environ", {"APP_ENV": "dev"}, clear=False):
            disabled = _Stub(data={"x": "val"}, when=When("${@env.app_env}") == "prod", tag="data")
            referencing = _StubUrl(url="${@data.x}")

            # disabled source contributes {} to context → "key not found" in sub-errors
            with pytest.raises(CrossRefExpandError) as exc_info:
                load(EnvSource(tag="env"), disabled, referencing, schema=_Cfg2)
            assert str(exc_info.value.exceptions[0]) == "key 'x' not found in 'data' data and no default provided"

    def test_when_lazy_disabled_with_default_succeeds(self):
        """${@tag.key:-default} works even when tag's source is disabled by when=."""

        @dataclass
        class _Cfg2:
            url: str = ""

        with patch.dict("os.environ", {"APP_ENV": "dev"}, clear=False):
            disabled = _Stub(data={"x": "val"}, when=When("${@env.app_env}") == "prod", tag="data")
            referencing = _StubUrl(url="${@data.x:-fallback_url}")
            result = load(EnvSource(tag="env"), disabled, referencing, schema=_Cfg2)
        assert result.url == "fallback_url"


class TestWhenTagCollision:
    def test_mutual_exclusive_when_no_collision(self, monkeypatch):
        """Two sources with same tag= and mutually exclusive when= → no error."""
        monkeypatch.setenv("APP_ENV", "prod")

        @dataclass
        class _Cfg2:
            token: str = ""

        result = load(
            _Stub(data={"token": "prod_token"}, tag="secrets", when=When("${APP_ENV}") == "prod"),
            _Stub(data={"token": "dev_token"}, tag="secrets", when=When("${APP_ENV}") == "dev"),
            schema=_Cfg2,
        )
        assert result.token == "prod_token"

    def test_both_enabled_same_referenced_tag_raises(self, monkeypatch):
        """Two sources with same tag=, both active, tag is cross-ref'd → DatureError."""
        monkeypatch.setenv("APP_ENV", "prod")

        @dataclass
        class _Cfg2:
            url: str = ""

        with pytest.raises(DatureError, match="Tag collision"):
            load(
                _Stub(data={"x": "a"}, tag="secrets", when=When("${APP_ENV}") == "prod"),
                _Stub(data={"x": "b"}, tag="secrets", when=When("${APP_ENV}") == "prod"),
                _StubUrl(url="${@secrets.x}"),
                schema=_Cfg2,
            )

    def test_explicit_tag_collision_without_cross_ref_raises(self):
        """Two sources with same explicit tag= and no cross-refs → DatureError."""
        with pytest.raises(DatureError, match="Tag collision"):
            load(
                _Stub(data={"x": "a"}, tag="s"),
                _Stub(data={"x": "b"}, tag="s"),
                schema=_WhenCfg,
            )


class TestDecoratorFootgun:
    def test_loader_init_does_not_read_env(self, monkeypatch):
        """Loader.__init__ must not evaluate when= — footgun fix.

        Old code: DatureError raised in __init__ when APP_ENV unset.
        New code: when= filter deferred to .load(), so construction always succeeds.
        """
        monkeypatch.delenv("APP_ENV", raising=False)

        # Must NOT raise — env is unset, but filter happens at .load() time.
        loader = Loader(
            _Stub(data={"x": "fallback"}),
            _Stub(data={"x": "prod_val"}, when=When("${APP_ENV}") == "prod"),
            schema=_WhenCfg,
        )

        # Now set env, then load — filter runs with correct env state.
        monkeypatch.setenv("APP_ENV", "prod")
        result = loader.load()
        assert result.x == "prod_val"

    def test_all_disabled_raises_at_load_not_init(self, monkeypatch):
        """when= all-filtered error surfaces on .load(), not on Loader construction."""
        monkeypatch.delenv("APP_ENV", raising=False)

        loader = Loader(
            _Stub(data={"x": "a"}, when=When("${APP_ENV}") == "prod"),
            schema=_WhenCfg,
        )

        # Should raise on .load(), not on Loader()
        with pytest.raises(DatureConfigError) as exc_info:
            loader.load()
        assert str(exc_info.value.exceptions[0]) == (
            "Loader requires at least one enabled Source (all sources filtered out by when=)"
        )


class TestValidationLoaderRuntimeSource:
    def test_validation_uses_runtime_last_source(self):
        """validation_loader must be built from the actual runtime last_source.

        Regression for latent bug: old code built validation_loader from init-time
        eager_filtered[-1]. If that source is lazy-when=disabled at runtime, the
        real last_source is different — validation would use the wrong retort.

        Concretely: source B (last in list) has lazy when= resolved to False, so
        source A becomes the actual last. We verify load succeeds and returns A's data.
        """

        @dataclass(kw_only=True, repr=False)
        class _StubB(dature.sources.base.Source):
            data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)
            format_name: ClassVar[str] = "stub_b"
            location_label: ClassVar[str] = "STUB"

            def _load(self) -> JSONValue:
                return dict(self.data)

        @dataclass
        class _CfgStr:
            x: str = ""

        with patch.dict("os.environ", {"FEAT": "off"}, clear=False):
            result = load(
                EnvSource(tag="env"),
                _Stub(data={"x": "from_a"}),
                _StubB(data={"x": "from_b"}, when=When("${@env.feat}") == "on"),
                schema=_CfgStr,
            )
        # B is lazy-disabled (FEAT=off), so A is the actual last_source.
        assert result.x == "from_a"


class TestLazyRevalidation:
    """W2: the decorator revalidation loader is built lazily, only on the slow path."""

    def test_load_does_not_build_revalidation(self, tmp_path: Path) -> None:
        json_file = tmp_path / "c.json"
        json_file.write_text('{"host": "h", "port": 5}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=False)

        loader.load()

        # Eager build_revalidation is removed — nothing needs it in function mode.
        assert loader.validation_loader is None
        # It is still available on demand for the decorator slow path.
        loader._ensure_revalidation()
        assert loader.validation_loader is not None

    def test_decorator_bad_explicit_override_still_revalidates(self, tmp_path: Path) -> None:
        json_file = tmp_path / "c.json"
        json_file.write_text('{"port": 5}')

        @load(JsonSource(file=json_file), cache=False)
        @dataclass
        class Cfg:
            port: Annotated[int, V >= 0]

        assert Cfg().port == 5

        with pytest.raises(DatureConfigError):
            Cfg(port=-1)
