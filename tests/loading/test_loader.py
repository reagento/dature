"""Unit tests for src/dature/loading/loader.py — the public ``Loader`` class."""

import dataclasses
import gc
import logging
import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import Flag
from io import BytesIO, StringIO
from pathlib import Path
from typing import Annotated, Any, assert_type, cast
from unittest.mock import patch

import pytest
import time_machine

import dature
import dature.sources.base
from dature import Dature, EnvFileSource, EnvSource, JsonSource, Loader, V, When, load
from dature.errors.exceptions import CrossRefExpandError, DatureConfigError, DatureError, FieldLoadError
from dature.loading.cache import cache_is_fresh
from dature.reloading.interval import FixedIntervalTrigger
from dature.reloading.protocol import ReloadContext, ReloadTriggerProtocol
from dature.reloading.scheduler import Scheduler
from dature.sources.base import Source
from dature.type_aliases import JSONValue


@dataclass
class _Config:
    host: str
    port: int


@dataclass(kw_only=True, repr=False)
class _Stub(dature.sources.base.Source):
    """Minimal in-memory source for when=/reload= tests. ``fail`` simulates a broken reload."""

    data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)
    fail: bool = False

    format_name: str = "stub"
    location_label: str = "STUB"

    def _load(self) -> JSONValue:
        if self.fail:
            msg = "stub source is broken"
            raise RuntimeError(msg)
        return dict(self.data)


@dataclass(kw_only=True, repr=False)
class _StubUrl(dature.sources.base.Source):
    """In-memory source that returns a single url key — used for cross-ref tests."""

    url: str = ""
    format_name: str = "stuburl"
    location_label: str = "STUB"

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


@dataclasses.dataclass
class _TgProxyConfig:
    url: str
    port: int


@dataclasses.dataclass
class _TgConfig:
    admins: list[int]
    use_proxy: bool
    proxy: _TgProxyConfig = dataclasses.field(default_factory=_TgProxyConfig)


@dataclasses.dataclass
class _ConfigWithDb:
    debug: bool = False
    db: dict[str, JSONValue] = dataclasses.field(default_factory=dict)
    tg: _TgConfig = dataclasses.field(default_factory=_TgConfig)


@dataclasses.dataclass(kw_only=True)
class _ConfigRequired:
    """Same shape as ``_ConfigWithDb`` but ``tg`` has no ``default_factory`` at all — the
    parity baseline: an unsafe ``default_factory`` must behave exactly like this."""

    debug: bool = False
    tg: _TgConfig


@dataclasses.dataclass
class _ConfigWithFactoryAndValidator:
    debug: Annotated[bool, V == True] = False  # noqa: E712
    tg: _TgConfig = dataclasses.field(default_factory=_TgConfig)


@dataclasses.dataclass
class _ConfigWithValidatorDirectlyOnFactoryField:
    """``tg`` itself carries a validator, so the field pass constructs it for real (via
    ``RetortCache.validator_target_types``) instead of leaving it a prunable dict — the case
    where ``tg``'s own nested unsafe factory (``proxy``) used to leak a bare ``TypeError``."""

    tg: Annotated[_TgConfig, V.check(lambda t: len(t.admins) > 0, error_message="need admins")]


class TestMissingDefaultFactorySection:
    """Regression: a section absent from every source, whose default_factory needs arguments,
    must be treated exactly like the same field declared without default_factory — required,
    with the normal missing-field error, enriched with which factory could not fill it in.
    See changes/+default-factory-missing-section.bugfix.md."""

    @pytest.mark.parametrize("schema", [_ConfigWithDb, _ConfigRequired], ids=["with-factory", "required"])
    def test_missing_section_reports_tg_on_both_schemas(self, schema: type) -> None:
        with pytest.raises(DatureConfigError) as exc_info:
            load(_Stub(data={"debug": True}), schema=schema)

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert [type(e) for e in errors] == [FieldLoadError]
        assert errors[0].field_path == ["tg"]

    def test_missing_section_message_names_factory_and_required_params(self) -> None:
        with pytest.raises(DatureConfigError) as exc_info:
            load(_Stub(data={"debug": True}), schema=_ConfigWithDb)

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert errors[0].message == (
            "Missing required field (its default_factory _TgConfig() cannot fill it in — "
            "_TgConfig itself requires admins, use_proxy)"
        )

    def test_fully_populated_section_loads_normally(self) -> None:
        result = load(
            _Stub(data={"debug": True, "tg": {"admins": [1], "use_proxy": True, "proxy": {"url": "x", "port": 1}}}),
            schema=_ConfigWithDb,
        )

        assert result.tg == _TgConfig(admins=[1], use_proxy=True, proxy=_TgProxyConfig(url="x", port=1))

    def test_partially_filled_section_reports_every_missing_field(self) -> None:
        with pytest.raises(DatureConfigError) as exc_info:
            load(_Stub(data={"debug": True, "tg": {"admins": [1]}}), schema=_ConfigWithDb)

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert {tuple(e.field_path) for e in errors} == {("tg", "use_proxy"), ("tg", "proxy")}

    def test_partial_section_and_unrelated_validator_failure_both_reported(self) -> None:
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                _Stub(data={"debug": False, "tg": {"admins": [1]}}),
                schema=_ConfigWithFactoryAndValidator,
            )

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert [type(e) for e in errors] == [FieldLoadError] * len(errors)
        assert {tuple(e.field_path) for e in errors} == {("debug",), ("tg", "use_proxy"), ("tg", "proxy")}

    def test_nested_unsafe_factory_reports_nested_path(self) -> None:
        with pytest.raises(DatureConfigError) as exc_info:
            load(_Stub(data={"debug": True, "tg": {"admins": [1], "use_proxy": True}}), schema=_ConfigWithDb)

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert len(errors) == 1
        assert errors[0].field_path == ["tg", "proxy"]

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"debug": True, "db": {"host": "h"}}, id="safe-factory-db-absent-fields"),
            pytest.param({}, id="no-fields-at-all"),
        ],
    )
    def test_safe_default_factories_contribute_no_errors_of_their_own(self, data: dict[str, JSONValue]) -> None:
        with pytest.raises(DatureConfigError) as exc_info:
            load(_Stub(data=data), schema=_ConfigWithDb)

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert [e.field_path for e in errors] == [["tg"]]

    def test_section_split_across_two_sources_loads_normally(self) -> None:
        result = load(
            _Stub(data={"debug": True, "tg": {"admins": [1], "use_proxy": True}}),
            _Stub(data={"tg": {"proxy": {"url": "x", "port": 1}}}),
            schema=_ConfigWithFactoryAndValidator,
        )

        assert result.tg == _TgConfig(admins=[1], use_proxy=True, proxy=_TgProxyConfig(url="x", port=1))

    def test_multisource_incomplete_section_reports_readable_message_not_typeerror(self) -> None:
        """A validator elsewhere in the schema used to force the multi-source field pass to
        construct ``tg`` for real from each source's partial raw dict, letting a bare
        ``TypeError`` from ``_TgConfig()`` leak out instead of a FieldLoadError."""

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                _Stub(data={"debug": True, "tg": {"admins": [1]}}),
                _Stub(data={}),
                schema=_ConfigWithFactoryAndValidator,
            )

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert [type(e) for e in errors] == [FieldLoadError] * len(errors)
        assert {tuple(e.field_path) for e in errors} == {("tg", "use_proxy"), ("tg", "proxy")}

    @pytest.mark.parametrize("schema", [_ConfigWithDb, _ConfigRequired], ids=["with-factory", "required"])
    def test_field_misplaced_at_root_of_second_source_reports_readable_message(self, schema: type) -> None:
        """The originally reported shape: two sources, no validator anywhere, and a subfield
        (``use_proxy``) mistakenly placed at the root of the second source instead of nested
        under ``tg``. Must report the normal missing-field error naming ``tg.use_proxy``, not a
        bare ``TypeError`` from ``_TgConfig()`` — identically whether or not ``tg`` itself
        declares an (unsafe) ``default_factory``."""

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                _Stub(data={"debug": True, "tg": {"admins": [1, 2, 3]}}),
                _Stub(data={"use_proxy": True}),
                skip_if_missing=True,
                schema=schema,
            )

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert [type(e) for e in errors] == [FieldLoadError] * len(errors)
        by_path = {tuple(e.field_path): e.message for e in errors}
        assert by_path.keys() == {("tg", "use_proxy"), ("tg", "proxy")}
        assert by_path[("tg", "use_proxy")] == "Missing required field"
        assert by_path[("tg", "proxy")] == (
            "Missing required field (its default_factory _TgProxyConfig() cannot fill it in — "
            "_TgProxyConfig itself requires url, port)"
        )

    def test_validator_on_factory_field_with_incomplete_nested_factory_reports_readable_message(self) -> None:
        """Regression: a validator attached directly to a section forces the field pass to
        construct it for real from each source's partial raw dict, so an unsafe default_factory
        nested *inside* that section used to leak the factory's bare ``TypeError`` text under the
        wrong field path instead of the normal missing-field error."""

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                _Stub(data={"tg": {"admins": [1]}}),
                _Stub(data={"tg": {"use_proxy": True}}),
                schema=_ConfigWithValidatorDirectlyOnFactoryField,
            )

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        by_path = {tuple(e.field_path): e.message for e in errors}
        assert by_path == {
            ("tg", "use_proxy"): "Missing required field",
            ("tg", "proxy"): "Missing required field",
        }


@dataclasses.dataclass
class _DeepInner:
    port: Annotated[int, V >= 0]


@dataclasses.dataclass
class _DeepOuter:
    inner: _DeepInner


@dataclasses.dataclass
class _ConfigDeepNestedValidator:
    debug: Annotated[bool, V == True] = False  # noqa: E712
    deep: _DeepOuter = dataclasses.field(default_factory=lambda: _DeepOuter(_DeepInner(port=0)))


class TestNestedSectionSplitAcrossSources:
    """Regression (C): a schema with any field validator used to break loading a valid config
    split across multiple sources, for sections unrelated to the validator itself — because the
    field pass constructed every nested dataclass for real from each source's partial raw dict.
    See changes/+nested-section-split-across-sources.bugfix.md."""

    def test_split_section_unrelated_to_validator_loads_normally(self) -> None:
        result = load(
            _Stub(data={"debug": True, "deep": {"inner": {"port": 1}}}),
            schema=_ConfigDeepNestedValidator,
        )

        assert result.deep.inner.port == 1

    def test_scalar_validator_inside_nested_dataclass_reports_deep_path(self) -> None:
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                _Stub(data={"debug": True, "deep": {"inner": {"port": -1}}}),
                schema=_ConfigDeepNestedValidator,
            )

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert {tuple(e.field_path) for e in errors} == {("deep", "inner", "port")}


class TestStaticTyping:
    """Static-only assertions — the checked behavior is verified by mypy/pyright, not at runtime."""

    def test_load_returns_schema_type(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 3000}')

        result = Loader(JsonSource(file=json_file), schema=_Config).load()
        assert_type(result, _Config)

    def test_as_decorator_returns_decorator(self) -> None:
        decorated = Loader.as_decorator(EnvSource())(_Config)
        assert_type(decorated, type[_Config])


class TestLoaderCache:
    @pytest.mark.parametrize(("cache_arg", "same_instance"), [(True, True), (False, False)], ids=["true", "false"])
    def test_cache_arg_controls_instance_reuse(self, tmp_path: Path, cache_arg: bool, same_instance: bool) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=cache_arg)

        first = loader.load()
        second = loader.load()

        assert (first is second) is same_instance

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


class TestLoaderCacheEngine:
    """``cache_engine`` controls whether the compiled retort survives past a ``.load()`` call —
    independent of ``cache``, which controls whether the *loaded result* is reused.
    """

    @pytest.mark.parametrize(
        ("cache_arg", "cache_engine_arg", "retains_engine"),
        [(True, False, False), (False, True, True)],
        ids=["default", "cache_engine_true"],
    )
    def test_cache_engine_arg_controls_engine_retention(
        self, tmp_path: Path, cache_arg: bool, cache_engine_arg: bool, retains_engine: bool
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=cache_arg, cache_engine=cache_engine_arg)

        loader.load()

        assert (loader._retort_cache._cache != {}) is retains_engine

    def test_cache_false_cache_engine_true_reuses_engine_across_loads(self, tmp_path: Path) -> None:
        """``cache=False, cache_engine=True`` re-reads on every call, without recompiling."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "original", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=False, cache_engine=True)

        first = loader.load()
        retort_after_first = next(iter(loader._retort_cache._cache.values()))
        json_file.write_text('{"host": "updated", "port": 2}')
        second = loader.load()
        retort_after_second = next(iter(loader._retort_cache._cache.values()))

        assert first.host == "original"
        assert second.host == "updated"
        assert retort_after_first is retort_after_second

    def test_cache_false_cache_engine_false_rebuilds_and_reloads(self, tmp_path: Path) -> None:
        """The cheapest-memory combination: no result cache, no engine cache — still correct."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "original", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=False, cache_engine=False)

        first = loader.load()
        json_file.write_text('{"host": "updated", "port": 2}')
        second = loader.load()

        assert first.host == "original"
        assert second.host == "updated"
        assert loader._retort_cache._cache == {}

    def test_cache_engine_none_falls_back_to_config_default(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache_engine=None)

        assert loader._cache_engine is False

    def test_decorator_default_still_loads_correctly(self, tmp_path: Path) -> None:
        """Decorator mode (default cache_engine=False) must keep working end-to-end."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')

        @dature.load(JsonSource(file=json_file), cache=True)
        @dataclass
        class Config:
            host: str
            port: int

        first = Config()
        second = Config()

        assert first.host == "h"
        assert first == second  # cache=True still reuses the loaded data


class TestLoaderStaleOnError:
    """``stale_on_error`` controls what happens when a reload (TTL expired) fails while a
    previously loaded config is cached: ``"keep"`` (default) and ``"retry"`` fall back to it,
    ``"raise"`` propagates the error (the library's original behavior).
    """

    @pytest.mark.parametrize(
        ("mode", "expect_raises"),
        [
            ("keep", False),
            ("retry", False),
            ("raise", True),
        ],
    )
    def test_reload_failure_after_ttl_expiry(
        self,
        tmp_path: Path,
        time_control: time_machine.Traveller,
        caplog: pytest.LogCaptureFixture,
        mode: str,
        expect_raises: bool,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=timedelta(seconds=10), stale_on_error=mode)

        first = loader.load()
        json_file.write_text("not json")
        time_control.shift(20.0)

        if expect_raises:
            with pytest.raises(DatureConfigError):
                loader.load()
            return

        with caplog.at_level("WARNING"):
            second = loader.load()

        assert second is first
        msgs = [r.getMessage() for r in caplog.records]
        assert len(msgs) == 1
        assert msgs[0].startswith("[_Config] Config reload failed, keeping the previously loaded config: ")

    def test_first_load_failure_always_raises(self, tmp_path: Path) -> None:
        # No previous successful load to fall back to — "keep" cannot help.
        json_file = tmp_path / "config.json"
        json_file.write_text("not json")

        with pytest.raises(DatureConfigError):
            Loader(JsonSource(file=json_file), schema=_Config, stale_on_error="keep").load()

    @pytest.mark.parametrize(
        ("mode", "expect_fresh"),
        [
            ("keep", True),
            ("retry", False),
        ],
    )
    def test_keep_restarts_ttl_window_retry_does_not(
        self,
        tmp_path: Path,
        time_control: time_machine.Traveller,
        mode: str,
        expect_fresh: bool,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=timedelta(seconds=10), stale_on_error=mode)
        loader.load()

        json_file.write_text("not json")
        time_control.shift(20.0)
        loader.load()

        # Still inside the failed reload's TTL window: "keep" restarted it (fresh, no re-read
        # attempted), "retry" left it stale (re-attempts the broken source every call).
        entry = loader._cache_entry
        assert entry is not None
        assert cache_is_fresh(cache=loader._cache, cached_at=entry.at) is expect_fresh

    def test_recovers_once_source_is_fixed(self, tmp_path: Path, time_control: time_machine.Traveller) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=timedelta(seconds=10), stale_on_error="keep")
        loader.load()

        json_file.write_text("not json")
        time_control.shift(20.0)
        stale = loader.load()

        json_file.write_text('{"host": "recovered", "port": 2}')
        time_control.shift(20.0)
        recovered = loader.load()

        assert stale.host == "h"
        assert recovered.host == "recovered"

    def test_stale_on_error_none_falls_back_to_config_default(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')

        loader = Loader(JsonSource(file=json_file), schema=_Config, stale_on_error=None)

        assert loader._stale_on_error == "keep"

    def test_unknown_mode_raises_value_error(self, tmp_path: Path, time_control: time_machine.Traveller) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')
        loader = Loader(JsonSource(file=json_file), schema=_Config, cache=timedelta(seconds=10), stale_on_error="bogus")
        loader.load()

        json_file.write_text("not json")
        time_control.shift(20.0)

        with pytest.raises(ValueError, match="Unknown stale_on_error mode"):
            loader.load()


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
            format_name: str = "tracked"
            location_label: str = "STUB"

            def _load(self) -> JSONValue:
                load_calls.append(self.name)
                return dict(self.data)

        result = load(
            _Tracked(name="disabled", data={"x": "secret"}, when=When("${APP_ENV}") == "prod"),
            _Tracked(name="active", data={"x": "ok"}),
            schema=_WhenCfg,
        )
        assert load_calls == ["active"]
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
            format_name: str = "stub_b"
            location_label: str = "STUB"

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


class ManualTrigger:
    """Test double for ``ReloadTriggerProtocol`` — deliberately does NOT inherit ``ReloadTrigger``.

    Proves custom triggers work via structural typing alone, and lets tests fire a reload
    synchronously (no sleeping, no real thread) by calling ``.fire()``.
    """

    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0
        self.context: ReloadContext | None = None
        self._on_trigger: Callable[[], None] | None = None

    def start(self, *, on_trigger: Callable[[], None], context: ReloadContext) -> None:
        if self._on_trigger is not None:
            msg = "ManualTrigger already started"
            raise RuntimeError(msg)
        self.start_count += 1
        self.context = context
        self._on_trigger = on_trigger

    def stop(self) -> None:
        self.stop_count += 1
        self._on_trigger = None

    def fire(self) -> None:
        assert self._on_trigger is not None, "fire() called before start()"
        self._on_trigger()


class TestLoaderReload:
    def test_reload_swaps_cached_instance(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        loader = Loader(source, schema=_Config, cache=True, reload=trigger)

        first = loader.load()
        source.data = {"host": "b", "port": 2}
        trigger.fire()
        second = loader.load()

        assert first == _Config(host="a", port=1)
        assert second == _Config(host="b", port=2)
        assert second is not first

    def test_on_reload_receives_new_instance(self) -> None:
        received: list[_Config] = []
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        loader = Loader(source, schema=_Config, cache=True, reload=trigger, on_reload=received.append)

        loader.load()
        source.data = {"host": "b", "port": 2}
        trigger.fire()

        assert received == [_Config(host="b", port=2)]

    @pytest.mark.parametrize("mode", ["keep", "retry", "raise"])
    def test_reload_failure_keeps_previous_instance(self, mode: str) -> None:
        errors: list[Exception] = []
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        loader = Loader(
            source,
            schema=_Config,
            cache=True,
            stale_on_error=mode,
            reload=trigger,
            on_error=errors.append,
        )

        loader.load()
        source.fail = True
        trigger.fire()

        assert loader.load() == _Config(host="a", port=1)
        assert len(errors) == 1
        messages = [str(errors[0]), *(str(e) for e in getattr(errors[0], "exceptions", ()))]
        if mode == "raise":
            assert messages == ["_Config loading errors (1)", "stub source is broken"]
        else:
            assert messages == ["stub source is broken"]

    def test_reload_starts_lazily(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        loader = Loader(source, schema=_Config, cache=True, reload=trigger)

        assert trigger.start_count == 0

        loader.load()

        assert trigger.start_count == 1

    def test_start_reload_is_idempotent(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        loader = Loader(source, schema=_Config, cache=True, reload=trigger)

        loader.start_reload()
        loader.start_reload()

        assert trigger.start_count == 1

    @pytest.mark.parametrize("call_load_first", [True, False])
    def test_stop_reload_is_idempotent(self, call_load_first: bool) -> None:
        # "Idempotent" per the protocol contract means safe/side-effect-free to call repeatedly
        # and even without a prior start() — not that Loader suppresses the forwarded stop()
        # calls itself. ManualTrigger.stop() is safe to call any number of times.
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        loader = Loader(source, schema=_Config, cache=True, reload=trigger)
        if call_load_first:
            loader.load()

        loader.stop_reload()
        loader.stop_reload()

        assert trigger.stop_count == 2

    def test_callback_exception_does_not_kill_reload(self, caplog: pytest.LogCaptureFixture) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()

        def _broken_on_reload(_: _Config) -> None:
            msg = "callback exploded"
            raise RuntimeError(msg)

        loader = Loader(source, schema=_Config, cache=True, reload=trigger, on_reload=_broken_on_reload)
        loader.load()
        source.data = {"host": "b", "port": 2}

        with caplog.at_level(logging.ERROR, logger="dature"):
            trigger.fire()

        assert loader.load() == _Config(host="b", port=2)
        assert [r.getMessage() for r in caplog.records] == ["[_Config] reload callback raised"]
        assert caplog.records[0].exc_info is not None
        assert caplog.records[0].exc_info[0] is RuntimeError

    def test_on_error_not_invoked_for_callback_failure(self) -> None:
        errors: list[Exception] = []
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()

        def _broken_on_reload(_: _Config) -> None:
            msg = "callback exploded"
            raise RuntimeError(msg)

        loader = Loader(
            source,
            schema=_Config,
            cache=True,
            reload=trigger,
            on_reload=_broken_on_reload,
            on_error=errors.append,
        )
        loader.load()
        source.data = {"host": "b", "port": 2}

        trigger.fire()

        assert errors == []

    def test_reload_recomputes_conditional_sources(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("APP_ENV", raising=False)
        dev_source = _Stub(data={"host": "dev-host", "port": 1}, when=When("${APP_ENV}") == "dev")
        prod_source = _Stub(data={"host": "prod-host", "port": 2}, when=When("${APP_ENV}") == "prod")
        trigger = ManualTrigger()
        monkeypatch.setenv("APP_ENV", "dev")
        loader = Loader(dev_source, prod_source, schema=_Config, cache=True, reload=trigger)

        first = loader.load()
        monkeypatch.setenv("APP_ENV", "prod")
        trigger.fire()

        assert first == _Config(host="dev-host", port=1)
        assert loader.load() == _Config(host="prod-host", port=2)

    def test_cache_true_reload_publishes_entry(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        loader = Loader(source, schema=_Config, cache=True, reload=trigger)

        loader.load()
        source.data = {"host": "b", "port": 2}
        trigger.fire()

        # Fast path (no lock) must see the reload-published entry.
        entry = loader._cache_entry
        assert entry is not None
        assert loader.load() is entry.data
        assert loader.load() == _Config(host="b", port=2)

    def test_cache_timedelta_with_reload_raises_explicit(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()

        with pytest.raises(ValueError, match="mutually exclusive"):
            Loader(source, schema=_Config, cache=timedelta(seconds=30), reload=trigger)

    def test_cache_timedelta_with_reload_raises_from_global_config(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        config = Dature(loading={"cache": timedelta(seconds=30)}).config

        with pytest.raises(ValueError, match="mutually exclusive"):
            Loader(source, schema=_Config, reload=trigger, config=config)

    def test_cache_false_reload_warns_and_does_not_publish(self, caplog: pytest.LogCaptureFixture) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()

        with caplog.at_level(logging.WARNING, logger="dature"):
            loader = Loader(source, schema=_Config, cache=False, reload=trigger)

        assert [r.getMessage() for r in caplog.records] == [
            (
                "[_Config] reload= has no effect on cached reads with cache=False — on_reload/on_error "
                "will still fire, but every load() call still does a full synchronous load."
            )
        ]
        loader.load()
        assert loader._cache_entry is None


@dataclass(kw_only=True, repr=False)
class _FakeRemoteClient:
    closed: bool = False

    def close(self) -> None:
        self.closed = True


@dataclass(kw_only=True, repr=False)
class _FakeRemoteSource(dature.sources.base.RemoteSource):
    """RemoteSource whose ``get_client()`` client-lifecycle can be observed from the outside."""

    data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)
    clients: list[_FakeRemoteClient] = dataclasses.field(default_factory=list)

    format_name: str = "fake-remote"
    location_label: str = "FAKE_REMOTE"

    def remote_address(self) -> str:
        return "fake-remote://stub"

    def _create_client(self) -> _FakeRemoteClient:
        client = _FakeRemoteClient()
        self.clients.append(client)
        return client

    def _close_client(self, client: object) -> None:
        cast("_FakeRemoteClient", client).close()

    def _fetch(self) -> JSONValue:
        with self.get_client():
            return dict(self.data)


class TestLoaderReloadClientLifecycle:
    def test_reload_ticks_never_leak_remote_clients(self) -> None:
        source = _FakeRemoteSource(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        loader = Loader(source, schema=_Config, cache=True, reload=trigger)

        loader.load()
        for i in range(5):
            source.data = {"host": f"host-{i}", "port": i}
            trigger.fire()

        assert loader.load() == _Config(host="host-4", port=4)
        assert len(source.clients) == 6
        assert all(client.closed for client in source.clients)


class TestLoaderReloadValidation:
    @pytest.mark.parametrize("loader_fn", [load, Dature().load])
    def test_function_mode_reload_raises(self, loader_fn: Callable[..., Any], tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "h", "port": 1}')

        with pytest.raises(ValueError, match="reload= has no effect in function mode"):
            loader_fn(JsonSource(file=json_file), schema=_Config, reload=ManualTrigger())

    @pytest.mark.parametrize("kwarg", ["on_reload", "on_error"])
    def test_callbacks_without_trigger_raise(self, kwarg: str) -> None:
        source = _Stub(data={"host": "a", "port": 1})

        with pytest.raises(ValueError, match="on_reload/on_error require reload="):
            Loader(source, schema=_Config, **{kwarg: lambda *_: None})

    def test_reload_rejects_non_trigger(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})

        with pytest.raises(TypeError, match="must implement ReloadTriggerProtocol"):
            Loader(source, schema=_Config, reload=object())

    def test_custom_protocol_trigger_accepted(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()

        assert isinstance(trigger, ReloadTriggerProtocol)
        assert not isinstance(trigger, dature.FixedIntervalTrigger)

        loader = Loader(source, schema=_Config, cache=True, reload=trigger)
        loader.load()
        source.data = {"host": "b", "port": 2}
        trigger.fire()

        assert loader.load() == _Config(host="b", port=2)


class TestLoaderReloadLifecycle:
    def test_loader_gc_unregisters_entry(self, scheduler: Scheduler) -> None:
        def _make() -> None:
            source = _Stub(data={"host": "a", "port": 1})
            trigger = FixedIntervalTrigger(interval=60, scheduler=scheduler)
            loader = Loader(source, schema=_Config, cache=True, reload=trigger)
            loader.load()

        _make()
        gc.collect()
        gc.collect()

        assert scheduler._entries == {}

    def test_failed_reload_does_not_leak_loader(self) -> None:
        source = _Stub(data={"host": "a", "port": 1})
        trigger = ManualTrigger()
        weak = None

        def _make() -> None:
            nonlocal weak
            loader = Loader(source, schema=_Config, cache=True, reload=trigger)
            loader.load()
            source.fail = True
            trigger.fire()
            weak = weakref.ref(loader)

        _make()
        gc.collect()
        gc.collect()

        assert weak is not None
        assert weak() is None

    def test_no_reload_leaves_no_thread(self) -> None:
        before = threading.active_count()
        source = _Stub(data={"host": "a", "port": 1})
        Loader(source, schema=_Config, cache=True).load()

        assert threading.active_count() == before
