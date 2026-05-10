"""Tests for loading/merge_config.py — load-level and config-group source merging."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

import pytest

from dature import Yaml12Source, configure
from dature.loading.merge_config import (
    SourceParams,
    apply_source_config_defaults,
    apply_source_init_params,
)
from dature.sources.base import Source
from dature.sources.env_ import EnvSource
from dature.types import JSONValue


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

    format_name = "_fake_remote"
    config_group: ClassVar[str | None] = "vault"

    def _load(self) -> JSONValue:
        return {}


@pytest.mark.usefixtures("_reset_config")
class TestApplySourceConfigDefaults:
    def test_noop_when_config_group_is_none(self, monkeypatch):
        monkeypatch.setattr(_FakeRemote, "config_group", None)
        configure(vault={"url": "http://x"})
        src = _FakeRemote(url=None)
        assert apply_source_config_defaults(src) is src

    def test_returns_same_instance_when_no_overrides(self):
        # Every overlapping field is set on the source, so the (non-None) VaultConfig defaults
        # have nothing to fill in → no overrides → same instance is returned.
        src = _FakeRemote(url="x", kv_version=1)
        result = apply_source_config_defaults(src)
        assert result is src

    def test_unrelated_config_field_ignored(self):
        # `mount_point` exists on VaultConfig but not on _FakeRemote — must not crash
        # nor add the attribute to the merged source
        configure(vault={"mount_point": "kv", "url": "http://x"})
        merged = apply_source_config_defaults(_FakeRemote())
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
        merged = apply_source_config_defaults(_FakeRemote(**instance_kwargs))
        assert getattr(merged, field) == expected
