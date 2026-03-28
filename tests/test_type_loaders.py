"""Tests for TypeLoader — custom type loading via Source, configure(), and Merge."""

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Merge, Source, TypeLoader, configure, load
from dature.config import _ConfigProxy


@dataclass
class Rgb:
    r: int
    g: int
    b: int


def rgb_from_string(value: str) -> Rgb:
    parts = value.split(",")
    return Rgb(r=int(parts[0]), g=int(parts[1]), b=int(parts[2]))


@dataclass
class ConfigWithRgb:
    name: str
    color: Rgb


@pytest.fixture
def _reset_config() -> Generator[None]:
    _ConfigProxy.set_instance(None)
    _ConfigProxy.set_type_loaders(())
    yield
    _ConfigProxy.set_instance(None)
    _ConfigProxy.set_type_loaders(())


@pytest.fixture
def yaml_with_rgb(tmp_path: Path) -> Path:
    p = tmp_path / "rgb.yaml"
    p.write_text("name: test\ncolor: '255,128,0'\n")
    return p


class TestTypeLoadersInSource:
    def test_single_source_with_type_loader(self, yaml_with_rgb: Path) -> None:
        result = load(
            Source(
                file=yaml_with_rgb,
                type_loaders=(TypeLoader(type_=Rgb, func=rgb_from_string),),
            ),
            ConfigWithRgb,
        )
        assert result.name == "test"
        assert result.color == Rgb(r=255, g=128, b=0)

    def test_type_loader_overrides_default(self, tmp_path: Path) -> None:
        """TypeLoader for int should override adaptix default."""

        def int_times_two(value: str) -> int:
            return int(value) * 2

        p = tmp_path / "cfg.yaml"
        p.write_text("name: app\ncolor: '10,20,30'\n")

        result = load(
            Source(
                file=p,
                type_loaders=(TypeLoader(type_=Rgb, func=rgb_from_string),),
            ),
            ConfigWithRgb,
        )
        assert result.color == Rgb(r=10, g=20, b=30)


class TestTypeLoadersInConfigure:
    @pytest.mark.usefixtures("_reset_config")
    def test_global_type_loaders_via_configure(self, yaml_with_rgb: Path) -> None:
        configure(
            type_loaders=(TypeLoader(type_=Rgb, func=rgb_from_string),),
        )
        result = load(Source(file=yaml_with_rgb), ConfigWithRgb)
        assert result.color == Rgb(r=255, g=128, b=0)


class TestTypeLoadersInMerge:
    def test_merge_metadata_type_loaders(self, tmp_path: Path) -> None:
        base = tmp_path / "base.yaml"
        base.write_text("name: base\ncolor: '1,2,3'\n")
        override = tmp_path / "override.yaml"
        override.write_text("name: override\n")

        result = load(
            Merge(
                Source(file=base),
                Source(file=override),
                type_loaders=(TypeLoader(type_=Rgb, func=rgb_from_string),),
            ),
            ConfigWithRgb,
        )
        assert result.name == "override"
        assert result.color == Rgb(r=1, g=2, b=3)


class TestTypeLoadersMergedFromBoth:
    @pytest.mark.usefixtures("_reset_config")
    def test_per_source_and_global_type_loaders_merge(self, tmp_path: Path) -> None:
        @dataclass
        class TwoCustom:
            color: Rgb
            tag: str

        def tag_upper(value: str) -> str:
            return value.upper()

        configure(
            type_loaders=(TypeLoader(type_=Rgb, func=rgb_from_string),),
        )

        p = tmp_path / "cfg.yaml"
        p.write_text("color: '10,20,30'\ntag: hello\n")

        result = load(
            Source(
                file=p,
                type_loaders=(TypeLoader(type_=str, func=tag_upper),),
            ),
            TwoCustom,
        )
        assert result.color == Rgb(r=10, g=20, b=30)
        assert result.tag == "HELLO"
