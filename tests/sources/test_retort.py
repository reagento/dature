from dataclasses import dataclass

import pytest
from adaptix import NameStyle as AdaptixNameStyle
from adaptix import Retort

from dature.field_path import F
from dature.sources.base import Source
from dature.sources.retort import (
    build_base_recipe,
    create_probe_retort,
    create_retort,
    create_validating_retort,
    ensure_retort,
    get_adaptix_name_style,
    get_name_mapping_providers,
    get_validator_providers,
    transform_to_dataclass,
)
from dature.types import JSONValue


@dataclass(kw_only=True)
class MockSource(Source):
    format_name = "mock"
    location_label = "MOCK"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data


class TestGetAdaptixNameStyle:
    @pytest.mark.parametrize(
        ("name_style", "expected"),
        [
            ("lower_snake", AdaptixNameStyle.LOWER_SNAKE),
            ("upper_snake", AdaptixNameStyle.UPPER_SNAKE),
            ("lower_camel", AdaptixNameStyle.CAMEL),
            ("upper_camel", AdaptixNameStyle.PASCAL),
            ("lower_kebab", AdaptixNameStyle.LOWER_KEBAB),
            ("upper_kebab", AdaptixNameStyle.UPPER_KEBAB),
        ],
    )
    def test_maps_style(self, name_style, expected):
        result = get_adaptix_name_style(name_style)

        assert result == expected

    def test_none_returns_none(self):
        result = get_adaptix_name_style(None)

        assert result is None


class TestGetNameMappingProviders:
    def test_none_none_returns_empty(self):
        result = get_name_mapping_providers(None, None)

        assert result == []

    def test_name_style_only(self):
        result = get_name_mapping_providers("lower_camel", None)

        assert len(result) == 1

    def test_field_mapping_with_field_path(self):
        @dataclass
        class Config:
            name: str

        field_mapping = {F[Config].name: "fullName"}
        result = get_name_mapping_providers(None, field_mapping)

        assert len(result) >= 1

    def test_field_mapping_with_string_owner(self):
        field_mapping = {F["Config"].name: "fullName"}
        result = get_name_mapping_providers(None, field_mapping)

        assert len(result) >= 1

    def test_combined_name_style_and_field_mapping(self):
        @dataclass
        class Config:
            user_name: str

        field_mapping = {F[Config].user_name: "full_name"}
        result = get_name_mapping_providers("lower_camel", field_mapping)

        assert len(result) >= 2

    def test_nested_field_path(self):
        @dataclass
        class Inner:
            city: str

        @dataclass
        class Outer:
            inner: Inner

        field_mapping = {F[Outer].inner.city: "cityName"}
        result = get_name_mapping_providers(None, field_mapping)

        assert len(result) >= 1


class TestGetValidatorProviders:
    def test_no_validators_returns_empty(self):
        @dataclass
        class Config:
            name: str
            port: int

        result = get_validator_providers(Config)

        assert result == []


class TestBuildBaseRecipe:
    def test_default_source(self):
        source = MockSource()
        result = build_base_recipe(source)

        assert len(result) > 0

    def test_with_resolved_type_loaders(self):
        source = MockSource()
        custom_loaders = {str: lambda x: str(x).upper()}

        result_default = build_base_recipe(source)
        result_custom = build_base_recipe(source, resolved_type_loaders=custom_loaders)

        assert len(result_custom) == len(result_default) + 1

    def test_with_source_type_loaders(self):
        source = MockSource(type_loaders={str: lambda x: str(x).upper()})

        result_with = build_base_recipe(source)
        result_without = build_base_recipe(MockSource())

        assert len(result_with) == len(result_without) + 1

    def test_resolved_type_loaders_override_source(self):
        source = MockSource(type_loaders={str: lambda _: "source"})
        resolved = {int: lambda x: x + 1}

        result = build_base_recipe(source, resolved_type_loaders=resolved)

        result_with_source_loaders = build_base_recipe(
            MockSource(type_loaders={str: lambda _: "source"}),
        )
        result_with_resolved = build_base_recipe(
            MockSource(),
            resolved_type_loaders=resolved,
        )

        assert len(result) == len(result_with_resolved)
        assert len(result) != len(result_with_source_loaders) or len(resolved) == len(source.type_loaders or {})


class TestCreateRetort:
    def test_returns_retort(self):
        source = MockSource()

        result = create_retort(source)

        assert isinstance(result, Retort)


class TestCreateProbeRetort:
    def test_returns_retort(self):
        source = MockSource()

        result = create_probe_retort(source)

        assert isinstance(result, Retort)


class TestCreateValidatingRetort:
    def test_returns_retort(self):
        @dataclass
        class Config:
            name: str

        source = MockSource()

        result = create_validating_retort(source, Config)

        assert isinstance(result, Retort)

    def test_with_root_validators(self):
        @dataclass
        class Config:
            name: str

        @dataclass(frozen=True, slots=True)
        class AlwaysTrue:
            def get_validator_func(self):
                return lambda _: True

            def get_error_message(self):
                return "always true"

        source = MockSource(root_validators=(AlwaysTrue(),))

        result = create_validating_retort(source, Config)

        assert isinstance(result, Retort)


class TestTransformToDataclass:
    def test_basic_transform(self):
        @dataclass
        class Config:
            name: str
            port: int

        source = MockSource()
        data = {"name": "TestApp", "port": 8080}

        result = transform_to_dataclass(source, data, Config)

        assert result == Config(name="TestApp", port=8080)

    def test_caches_retort(self):
        @dataclass
        class Config:
            name: str

        source = MockSource()
        assert Config not in source.retorts

        transform_to_dataclass(source, {"name": "a"}, Config)

        assert Config in source.retorts

    def test_reuses_cached_retort(self):
        @dataclass
        class Config:
            name: str

        source = MockSource()
        transform_to_dataclass(source, {"name": "a"}, Config)
        cached = source.retorts[Config]

        transform_to_dataclass(source, {"name": "b"}, Config)

        assert source.retorts[Config] is cached


class TestEnsureRetort:
    def test_creates_retort(self):
        @dataclass
        class Config:
            name: str

        source = MockSource()
        assert Config not in source.retorts

        ensure_retort(source, Config)

        assert Config in source.retorts

    def test_does_not_overwrite_existing(self):
        @dataclass
        class Config:
            name: str

        source = MockSource()
        ensure_retort(source, Config)
        existing = source.retorts[Config]

        ensure_retort(source, Config)

        assert source.retorts[Config] is existing
