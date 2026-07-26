"""Tests for loading/merge_runtime.py — load-level and config-group source merging."""

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

from dature import F, JsonSource, When, Yaml12Source, configure, load
from dature.errors.exceptions import DatureError
from dature.loading.merge_runtime import (
    MergeConfig,
    SourceParams,
    apply_source_config_group,
    apply_source_init_params,
    resolve_skip_invalid,
    should_skip_broken,
    should_skip_missing,
)
from dature.sources.base import Source
from dature.sources.env_ import EnvSource
from dature.type_aliases import JSONValue, SkipFieldsInvalid


class TestApplySourceInitParamsNestedStrategy:
    @pytest.mark.parametrize(
        ("source_strategy", "load_strategy", "expected"),
        [
            (None, "json", "json"),
            ("flat", "json", "flat"),
            ("json", "flat", "json"),
            (None, None, "flat"),
        ],
        ids=[
            "source-none-uses-load-level",
            "source-explicit-flat-overrides-load-level",
            "source-explicit-json-overrides-load-level",
            "source-none-no-load-level-uses-config-default",
        ],
    )
    def test_resolve(
        self,
        source_strategy: str | None,
        load_strategy: str | None,
        expected: str,
    ):
        kwargs = {} if source_strategy is None else {"nested_resolve_strategy": source_strategy}
        source = EnvSource(**kwargs)

        result = apply_source_init_params(source, SourceParams(nested_resolve_strategy=load_strategy))

        assert result.nested_resolve_strategy == expected


class TestApplySourceInitParamsFilePathCache:
    def test_overrides_invalidate_resolved_file_path_cache(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\n")

        source = Yaml12Source(file="config.yaml")

        # Before overrides: same call falls back to Path(self.file).
        assert source.file_path_for_errors() == Path("config.yaml")

        result = apply_source_init_params(
            source,
            SourceParams(search_system_paths=True, system_config_dirs=(tmp_path,)),
        )

        # After overrides: same call now resolves via the system-path search,
        # proving the stale cache was invalidated.
        assert result.file_path_for_errors() == config_file


@dataclass(kw_only=True, repr=False)
class _FakeRemote(Source):
    url: str | None = None
    kv_version: Literal[1, 2] | None = None
    irrelevant: str | None = None

    format_name: str = "_fake_remote"
    config_group: str | None = "vault"

    def _load(self) -> JSONValue:
        return {}


@pytest.mark.usefixtures("_reset_config")
class TestApplySourceConfigGroup:
    def test_noop_when_config_group_is_none(self):
        configure(vault={"url": "http://x"})
        src = _FakeRemote(url=None, config_group=None)
        assert apply_source_config_group(src) is src

    def test_returns_same_instance_when_no_overrides(self):
        # Every overlapping field is set on the source, so the (non-None) VaultConfig defaults
        # have nothing to fill in → no overrides → same instance is returned.
        src = _FakeRemote(url="x", kv_version=1)
        result = apply_source_config_group(src)
        assert result is src

    def test_unrelated_config_field_ignored(self):
        # `mount_point` exists on VaultConfig but not on _FakeRemote — must not crash
        # nor add the attribute to the merged source
        configure(vault={"mount_point": "kv", "url": "http://x"})
        merged = apply_source_config_group(_FakeRemote())
        assert merged.url == "http://x"
        assert not hasattr(merged, "mount_point")

    @pytest.mark.parametrize(
        ("instance_kwargs", "config_kwargs", "field", "expected"),
        [
            pytest.param({"url": None}, {"url": "http://x"}, "url", "http://x", id="config_fills_none"),
            pytest.param(
                {"url": "http://instance"},
                {"url": "http://config"},
                "url",
                "http://instance",
                id="instance_wins_over_config",
            ),
            pytest.param({}, {"url": "u", "kv_version": 1}, "kv_version", 1, id="kv_version_v1_from_config"),
            pytest.param({}, {"url": "u", "kv_version": 2}, "kv_version", 2, id="kv_version_v2_from_config"),
            pytest.param(
                {},
                {"url": "u"},
                "irrelevant",
                None,
                id="source_only_field_stays_none_when_config_silent",
            ),
        ],
    )
    def test_field_resolution(self, instance_kwargs, config_kwargs, field, expected):
        configure(vault=config_kwargs)
        merged = apply_source_config_group(_FakeRemote(**instance_kwargs))
        assert getattr(merged, field) == expected


class TestShouldSkipBroken:
    @pytest.mark.parametrize(
        ("skip_if_broken", "merge_skip_if_broken", "expected"),
        [
            (True, False, True),
            (False, True, False),
            (None, True, True),
        ],
        ids=["source-true", "source-false", "source-none-uses-merge"],
    )
    def test_resolve(
        self,
        tmp_path: Path,
        skip_if_broken: bool | None,
        merge_skip_if_broken: bool,
        expected: bool,
    ):
        json_file = tmp_path / "c.json"
        json_file.write_text("{}")
        kwargs = {} if skip_if_broken is None else {"skip_if_broken": skip_if_broken}
        source = JsonSource(file=json_file, **kwargs)
        merge = MergeConfig(sources=(source,), skip_if_broken=merge_skip_if_broken)

        assert should_skip_broken(source, merge) is expected

    def test_env_source_raises(self):
        with pytest.raises(TypeError, match="unexpected keyword argument 'skip_if_broken'"):
            EnvSource(skip_if_broken=True)


class TestShouldSkipMissing:
    @pytest.mark.parametrize(
        ("skip_if_missing", "merge_skip_if_missing", "expected"),
        [
            (True, False, True),
            (False, True, False),
            (None, True, True),
        ],
        ids=["source-true", "source-false", "source-none-uses-merge"],
    )
    def test_resolve(
        self,
        tmp_path: Path,
        skip_if_missing: bool | None,
        merge_skip_if_missing: bool,
        expected: bool,
    ):
        json_file = tmp_path / "c.json"
        json_file.write_text("{}")
        kwargs = {} if skip_if_missing is None else {"skip_if_missing": skip_if_missing}
        source = JsonSource(file=json_file, **kwargs)
        merge = MergeConfig(sources=(source,), skip_if_missing=merge_skip_if_missing)

        assert should_skip_missing(source, merge) is expected

    def test_env_source_raises(self):
        with pytest.raises(TypeError, match="unexpected keyword argument 'skip_if_missing'"):
            EnvSource(skip_if_missing=True)


class TestResolveSkipInvalid:
    @pytest.mark.parametrize(
        ("source_skip", "merge_skip", "expected"),
        [
            (F.ANY, [], F.ANY),
            (None, F.ANY, F.ANY),
        ],
        ids=["source-overrides", "source-none-inherits"],
    )
    def test_resolve(
        self,
        tmp_path: Path,
        source_skip: SkipFieldsInvalid,
        merge_skip: SkipFieldsInvalid,
        expected: SkipFieldsInvalid,
    ):
        json_file = tmp_path / "c.json"
        json_file.write_text("{}")
        kwargs = {} if source_skip is None else {"skip_field_if_invalid": source_skip}
        source = JsonSource(file=json_file, **kwargs)
        merge = MergeConfig(sources=(source,), skip_field_if_invalid=merge_skip)

        assert resolve_skip_invalid(source, merge) is expected


@dataclass(kw_only=True, repr=False)
class _StubSource(Source):
    """Minimal in-memory source that returns its own data field."""

    data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)
    format_name: str = "stubmr"
    location_label: str = "STUBMR"

    def _load(self) -> JSONValue:
        return dict(self.data)


@dataclass
class _ValCfg:
    value: str = ""


class TestEvalLazyWhen:
    """Unit coverage for LoadCtx._eval_lazy_when via the full load() path."""

    def test_lazy_when_enabled_when_context_matches(self) -> None:
        result = load(
            _StubSource(data={"value": "from-stub"}, when=When("${@ctrl.mode}") == "active", tag="stub"),
            _StubSource(data={"mode": "active"}, tag="ctrl"),
            schema=_ValCfg,
        )
        assert result.value == "from-stub"

    def test_lazy_when_disabled_when_context_not_matched(self) -> None:
        result = load(
            _StubSource(data={"value": "should-not-load"}, when=When("${@ctrl.mode}") == "active", tag="stub"),
            _StubSource(data={"mode": "inactive", "value": "fallback"}, tag="ctrl"),
            schema=_ValCfg,
        )
        assert result.value == "fallback"


@dataclass(kw_only=True, repr=False)
class _StubSourceB(Source):
    """Second stub variant — same format_name as _StubSource so they share resolved_tag."""

    data: dict[str, JSONValue] = dataclasses.field(default_factory=dict)
    format_name: str = "stubmr"  # same as _StubSource → same resolved_tag when tag= unset
    location_label: str = "STUBMRB"

    def _load(self) -> JSONValue:
        return dict(self.data)


class TestCheckLazyTagCollision:
    """Unit coverage for LoadCtx._check_lazy_tag_collision via the full load() path.

    The static _build_dep_graph collision check only fires when the shared tag is
    referenced by ${@...} refs or when sources use an explicit tag=.  When both sources
    share a tag *implicitly* (same format_name, no tag=) and neither is referenced,
    the static check treats it as inactive — only the dynamic check in LoadCtx fires
    when both lazy when= conditions evaluate True at load time.
    """

    def test_collision_when_both_lazy_enabled(self) -> None:
        # Both sources share resolved_tag="stubmr" (via format_name) and pass their lazy when=.
        with pytest.raises(DatureError, match="Tag collision among enabled sources"):
            load(
                _StubSource(data={"value": "a"}, when=When("${@ctrl.flag}") == "yes"),
                _StubSourceB(data={"value": "b"}, when=When("${@ctrl.flag}") == "yes"),
                _StubSource(data={"flag": "yes"}, tag="ctrl"),
                schema=_ValCfg,
            )

    def test_no_collision_when_one_lazy_disabled(self) -> None:
        # Only one source's lazy condition is met, so no collision.
        result = load(
            _StubSource(data={"value": "active"}, when=When("${@ctrl.flag}") == "yes"),
            _StubSourceB(data={"value": "inactive"}, when=When("${@ctrl.flag}") == "no"),
            _StubSource(data={"flag": "yes"}, tag="ctrl"),
            schema=_ValCfg,
        )
        assert result.value == "active"
