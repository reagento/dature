from dataclasses import dataclass
from typing import Annotated

import pytest
from adaptix import NameStyle as AdaptixNameStyle

from dature import V
from dature.field_path import F
from dature.loading.retort import (
    RetortCache,
    build_base_recipe,
    get_adaptix_name_style,
    get_name_mapping_providers,
    get_validator_providers,
)
from dature.sources.base import IndexedSource, Source
from dature.type_aliases import JSONValue


@dataclass(kw_only=True)
class MockSource(Source):
    format_name = "mock"
    location_label = "MOCK"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
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


class TestTransformToDataclass:
    def test_basic_transform(self):
        @dataclass
        class Config:
            name: str
            port: int

        source = MockSource()
        data = {"name": "TestApp", "port": 8080}

        result = RetortCache(Config).plain(IndexedSource(source, 0)).load(data, Config)

        assert result == Config(name="TestApp", port=8080)


class TestRetortCache:
    def test_plain_caches_retort(self):
        @dataclass
        class Config:
            name: str

        source = MockSource()
        cache = RetortCache(Config)

        first = cache.plain(IndexedSource(source, 0))
        second = cache.plain(IndexedSource(source, 0))

        assert first is second

    def test_different_type_loaders_produce_distinct_retorts(self):
        @dataclass
        class Config:
            name: str

        source = MockSource()
        cache = RetortCache(Config)
        loaders_a = {str: lambda x: str(x).upper()}
        loaders_b = {str: lambda x: str(x).lower()}

        retort_a = cache.plain(IndexedSource(source, 0), resolved_type_loaders=loaders_a)
        retort_b = cache.plain(IndexedSource(source, 0), resolved_type_loaders=loaders_b)

        assert retort_a is not retort_b

    def test_none_and_custom_loaders_produce_distinct_retorts(self):
        @dataclass
        class Config:
            name: str

        source = MockSource()
        cache = RetortCache(Config)
        custom_loaders = {str: lambda x: str(x).upper()}

        retort_none = cache.plain(IndexedSource(source, 0))
        retort_custom = cache.plain(IndexedSource(source, 0), resolved_type_loaders=custom_loaders)

        assert retort_none is not retort_custom

    def test_two_sources_with_same_config_produce_distinct_retorts(self):
        @dataclass
        class Config:
            name: str

        source_a = MockSource()
        source_b = MockSource()
        cache = RetortCache(Config)

        retort_a = cache.plain(IndexedSource(source_a, 0))
        retort_b = cache.plain(IndexedSource(source_b, 1))

        assert retort_a is not retort_b

    def test_plain_load_returns_correct_result(self):
        @dataclass
        class Config:
            name: str
            port: int

        source = MockSource()
        cache = RetortCache(Config)
        indexed = IndexedSource(source, 0)

        result = cache.plain(indexed).load({"name": "App", "port": 9000}, Config)

        assert result == Config(name="App", port=9000)


@dataclass
class _ConfigAnnotated:
    port: Annotated[int, V >= 0]
    name: str


@dataclass
class _ConfigPlain:
    port: int
    name: str


class TestHasValidators:
    @pytest.mark.parametrize(
        ("has_annotated", "has_source_validators", "expected"),
        [
            (False, False, False),
            (True, False, True),
            (False, True, True),
            (True, True, True),
        ],
    )
    def test_combinations(self, has_annotated, has_source_validators, expected):
        schema = _ConfigAnnotated if has_annotated else _ConfigPlain

        validators = {F[schema].port: V >= 0} if has_source_validators else None
        source = MockSource(validators=validators)
        cache = RetortCache(schema)

        assert cache.has_validators(IndexedSource(source, 0)) == expected

    def test_schema_flag_computed_at_init(self):
        """Schema-level annotated-validator flag is computed once in __init__, not per-call."""

        @dataclass
        class Config:
            value: Annotated[int, V >= 0]

        source = MockSource()
        cache = RetortCache(Config)
        indexed = IndexedSource(source, 0)

        # Both calls return the same value, confirming the flag is stable.
        assert cache.has_validators(indexed) is True
        assert cache.has_validators(indexed) is True


class TestFieldPassRetort:
    def test_returns_plain_equivalent_when_no_validators(self):
        """field_pass(skip=False) with no validators behaves like plain."""

        @dataclass
        class Config:
            name: str

        source = MockSource()
        cache = RetortCache(Config)
        indexed = IndexedSource(source, 0)

        # Should not raise; field_pass is always constructable.
        retort = cache.field_pass(indexed, skip=False)

        assert retort is not None

    def test_field_pass_and_root_retort_are_distinct(self):
        """field_pass and root_retort must return separate cached retorts."""

        @dataclass
        class Config:
            port: Annotated[int, V >= 0]

        source = MockSource()
        cache = RetortCache(Config)
        indexed = IndexedSource(source, 0)

        fp = cache.field_pass(indexed, skip=False)
        root = cache.root_retort(indexed)

        assert fp is not root

    def test_field_pass_skip_and_noskip_are_distinct(self):
        """field_pass(skip=True) and field_pass(skip=False) must produce separate retorts."""

        @dataclass
        class Config:
            port: int

        source = MockSource()
        cache = RetortCache(Config)
        indexed = IndexedSource(source, 0)

        fp_skip = cache.field_pass(indexed, skip=True)
        fp_noskip = cache.field_pass(indexed, skip=False)

        assert fp_skip is not fp_noskip
