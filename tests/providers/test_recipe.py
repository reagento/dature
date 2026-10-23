"""Tests for providers/recipe.py."""

from dataclasses import dataclass

import pytest
from adaptix import NameStyle as AdaptixNameStyle
from adaptix import loader
from adaptix.provider import Provider

from dature import ConsulSource, VaultSource
from dature.field_path import F
from dature.providers.recipe import (
    FAST_BYTES,
    FAST_PLAIN,
    FAST_REMOTE,
    FAST_STRING,
    build_base_recipe,
    get_adaptix_name_style,
    get_name_mapping_providers,
    uncustomized_fast_retort,
)
from dature.sources.base import FlatKeySource, Source, bytes_value_loaders, remote_value_loaders, string_value_loaders
from dature.type_aliases import JSONValue


@dataclass(kw_only=True)
class MockSource(Source):
    format_name: str = "mock"
    location_label: str = "MOCK"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data


@dataclass(kw_only=True)
class MockFlatKeySource(FlatKeySource):
    format_name: str = "mock_flat"
    location_label: str = "MOCK FLAT"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data


@dataclass(kw_only=True)
class MockCustomLoadersSource(Source):
    """A source with its own distinct, non-empty recipe — must never match a precomputed constant."""

    format_name: str = "mock_custom"
    location_label: str = "MOCK CUSTOM"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data

    def format_loaders(self) -> "list[Provider]":
        return [loader(int, lambda x: int(x))]  # noqa: PLW0108


@dataclass(kw_only=True)
class MockStringRecipeSource(Source):
    """A plain ``Source`` subclass (not ``FlatKeySource``) that itself returns the canonical
    string-value recipe — proves the fast-path detection is class-agnostic, matching by content."""

    format_name: str = "mock_string_recipe"
    location_label: str = "MOCK STRING RECIPE"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data

    def format_loaders(self) -> "list[Provider]":
        return string_value_loaders()


@dataclass(kw_only=True)
class MockRawRecipeSource(Source):
    """A plain ``Source`` subclass returning the canonical raw-value recipe (Consul's
    decode="raw"), proving the fast-path detection matches FAST_BYTES by content too."""

    format_name: str = "mock_raw_recipe"
    location_label: str = "MOCK RAW RECIPE"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data

    def format_loaders(self) -> "list[Provider]":
        return bytes_value_loaders()


@dataclass(kw_only=True)
class MockRemoteRecipeSource(Source):
    """A plain ``Source`` subclass returning the canonical native-JSON remote recipe (Vault,
    Consul decode="json"), proving the fast-path detection matches FAST_REMOTE by content too."""

    format_name: str = "mock_remote_recipe"
    location_label: str = "MOCK REMOTE RECIPE"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data

    def format_loaders(self) -> "list[Provider]":
        return remote_value_loaders()


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

    def test_unknown_style_raises(self):
        with pytest.raises(ValueError, match="Unknown name_style: 'bogus'") as exc_info:
            get_adaptix_name_style("bogus")

        assert str(exc_info.value) == "Unknown name_style: 'bogus'"


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

        result = get_name_mapping_providers(None, {F[Config].name: "fullName"})

        assert len(result) == 2

    def test_field_mapping_with_string_owner(self):
        result = get_name_mapping_providers(None, {F["Config"].name: "fullName"})

        assert len(result) == 2

    def test_combined_name_style_and_field_mapping(self):
        @dataclass
        class Config:
            user_name: str

        result = get_name_mapping_providers("lower_camel", {F[Config].user_name: "full_name"})

        assert len(result) == 3

    def test_nested_field_path(self):
        @dataclass
        class Inner:
            city: str

        @dataclass
        class Outer:
            inner: Inner

        result = get_name_mapping_providers(None, {F[Outer].inner.city: "cityName"})

        assert len(result) == 2


class TestBuildBaseRecipe:
    def test_default_source(self):
        result = build_base_recipe(MockSource())

        assert len(result) > 0

    def test_with_resolved_type_loaders(self):
        custom_loaders = {str: lambda x: str(x).upper()}

        result_default = build_base_recipe(MockSource())
        result_custom = build_base_recipe(MockSource(), resolved_type_loaders=custom_loaders)

        assert len(result_custom) == len(result_default) + 1

    def test_with_source_type_loaders(self):
        result_with = build_base_recipe(MockSource(type_loaders={str: lambda x: str(x).upper()}))
        result_without = build_base_recipe(MockSource())

        assert len(result_with) == len(result_without) + 1

    def test_resolved_type_loaders_override_source(self):
        resolved = {int: lambda x: x + 1}

        result = build_base_recipe(MockSource(type_loaders={str: lambda _: "source"}), resolved_type_loaders=resolved)
        result_with_resolved = build_base_recipe(MockSource(), resolved_type_loaders=resolved)

        assert len(result) == len(result_with_resolved)


class TestUncustomizedFastRetort:
    """Uncustomized sources reuse a precomputed module-level FAST retort instead of extending.

    Detection is by content, not by class: a source is matched by what ``format_loaders()``
    returns, regardless of its type in the ``Source`` hierarchy.
    """

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            (MockSource(), FAST_PLAIN),
            (MockFlatKeySource(), FAST_STRING),
            # A plain `Source` subclass that itself returns the canonical string-value recipe
            # matches FAST_STRING too — proves detection doesn't key off FlatKeySource.
            (MockStringRecipeSource(), FAST_STRING),
            # Same proof for the raw-value recipe (Consul's decode="raw").
            (MockRawRecipeSource(), FAST_BYTES),
            # Same proof for the native-JSON remote recipe (Vault, Consul decode="json").
            (MockRemoteRecipeSource(), FAST_REMOTE),
        ],
    )
    def test_uncustomized_source_matches_by_recipe_content(self, source, expected):
        assert uncustomized_fast_retort(source) is expected

    @pytest.mark.parametrize(
        "source",
        [
            MockSource(type_loaders={str: lambda x: str(x).upper()}),
            MockSource(name_style="lower_camel"),
            MockFlatKeySource(type_loaders={str: lambda x: str(x).upper()}),
        ],
    )
    def test_customized_source_returns_none(self, source):
        assert uncustomized_fast_retort(source) is None

    def test_field_mapping_returns_none(self):
        @dataclass
        class Config:
            name: str

        source = MockSource(field_mapping={F[Config].name: "fullName"})

        assert uncustomized_fast_retort(source) is None

    def test_distinct_nonempty_recipe_returns_none(self):
        """A source with its own, different non-empty recipe matches neither constant."""
        assert uncustomized_fast_retort(MockCustomLoadersSource()) is None

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            pytest.param(ConsulSource(host="c", path="p", decode="utf-8"), FAST_STRING, id="consul_utf8"),
            pytest.param(ConsulSource(host="c", path="p", decode="json"), FAST_REMOTE, id="consul_json"),
            pytest.param(ConsulSource(host="c", path="p", decode="raw"), FAST_BYTES, id="consul_raw"),
            pytest.param(VaultSource(host="u", token="t", path="p"), FAST_REMOTE, id="vault"),
        ],
    )
    def test_real_remote_sources_match_by_recipe_content(self, source, expected):
        """Consul and Vault stay on a precomputed fast retort, never paying per-call .extend()."""
        assert uncustomized_fast_retort(source) is expected
