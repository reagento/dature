"""Tests for TypeLoader — custom type loading via Source, Dature(), and load()."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Yaml12Source, load
from dature.instance import Dature
from dature.type_aliases import TypeLoaderMap


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
def yaml_with_rgb(tmp_path: Path) -> Path:
    p = tmp_path / "rgb.yaml"
    p.write_text("name: test\ncolor: '255,128,0'\n")
    return p


class TestTypeLoadersInSource:
    def test_single_source_with_type_loader(self, yaml_with_rgb: Path) -> None:
        result = load(
            Yaml12Source(
                file=yaml_with_rgb,
                type_loaders={Rgb: rgb_from_string},
            ),
            schema=ConfigWithRgb,
        )
        assert result.name == "test"
        assert result.color == Rgb(r=255, g=128, b=0)


class TestInstanceTypeLoaders:
    def test_instance_type_loaders(self, yaml_with_rgb: Path) -> None:
        """Dature(type_loaders=...) applies to all loads made through the instance."""
        app = Dature(type_loaders={Rgb: rgb_from_string})
        result = app.load(Yaml12Source(file=yaml_with_rgb), schema=ConfigWithRgb)
        assert result.color == Rgb(r=255, g=128, b=0)

    def test_two_instances_with_different_type_loaders_independent(self, tmp_path: Path) -> None:
        """Two Dature instances with different type_loaders do not interfere."""

        @dataclass
        class OnlyRgb:
            color: Rgb

        @dataclass
        class NoCustom:
            name: str

        rgb_file = tmp_path / "rgb.yaml"
        rgb_file.write_text("color: '10,20,30'\n")
        name_file = tmp_path / "name.yaml"
        name_file.write_text("name: hello\n")

        rgb_app = Dature(type_loaders={Rgb: rgb_from_string})
        plain_app = Dature()

        result = rgb_app.load(Yaml12Source(file=rgb_file), schema=OnlyRgb)
        assert result.color == Rgb(r=10, g=20, b=30)

        plain_result = plain_app.load(Yaml12Source(file=name_file), schema=NoCustom)
        assert plain_result.name == "hello"

    def test_mutating_source_dict_after_construction_does_not_affect_instance(self, yaml_with_rgb: Path) -> None:
        """Dature copies type_loaders at construction — later mutating the caller's dict is inert."""
        source_loaders: TypeLoaderMap = {Rgb: rgb_from_string}
        app = Dature(type_loaders=source_loaders)

        def rgb_all_zero(_value: str) -> Rgb:
            return Rgb(r=0, g=0, b=0)

        source_loaders[Rgb] = rgb_all_zero
        source_loaders[str] = str.upper

        result = app.load(Yaml12Source(file=yaml_with_rgb), schema=ConfigWithRgb)
        assert result.color == Rgb(r=255, g=128, b=0)

    def test_replace_copies_type_loaders_independent_of_base_and_caller_dict(self, yaml_with_rgb: Path) -> None:
        """replace(type_loaders=...) does not share a mutable mapping with the base instance or caller."""
        base = Dature(type_loaders={Rgb: rgb_from_string})

        def rgb_all_zero(_value: str) -> Rgb:
            return Rgb(r=0, g=0, b=0)

        derived_loaders = {Rgb: rgb_all_zero}
        derived = base.replace(type_loaders=derived_loaders)

        derived_loaders[Rgb] = lambda _value: Rgb(r=9, g=9, b=9)

        base_result = base.load(Yaml12Source(file=yaml_with_rgb), schema=ConfigWithRgb)
        derived_result = derived.load(Yaml12Source(file=yaml_with_rgb), schema=ConfigWithRgb)

        assert base_result.color == Rgb(r=255, g=128, b=0)
        assert derived_result.color == Rgb(r=0, g=0, b=0)


class TestTypeLoadersInMerge:
    def test_merge_metadata_type_loaders(self, tmp_path: Path) -> None:
        base = tmp_path / "base.yaml"
        base.write_text("name: base\ncolor: '1,2,3'\n")
        override = tmp_path / "override.yaml"
        override.write_text("name: override\n")

        result = load(
            Yaml12Source(file=base),
            Yaml12Source(file=override),
            schema=ConfigWithRgb,
            type_loaders={Rgb: rgb_from_string},
        )
        assert result.name == "override"
        assert result.color == Rgb(r=1, g=2, b=3)


class TestTypeLoadersMergedFromBoth:
    def test_per_source_and_instance_type_loaders_merge(self, tmp_path: Path) -> None:
        @dataclass
        class TwoCustom:
            color: Rgb
            tag: str

        def tag_upper(value: str) -> str:
            return value.upper()

        p = tmp_path / "cfg.yaml"
        p.write_text("color: '10,20,30'\ntag: hello\n")

        app = Dature(type_loaders={Rgb: rgb_from_string})
        result = app.load(
            Yaml12Source(
                file=p,
                type_loaders={str: tag_upper},
            ),
            schema=TwoCustom,
        )
        assert result.color == Rgb(r=10, g=20, b=30)
        assert result.tag == "HELLO"
