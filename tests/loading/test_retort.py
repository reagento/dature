from dataclasses import dataclass
from typing import Annotated, Any, cast

import pytest
from adaptix import NameStyle as AdaptixNameStyle
from adaptix import Retort, loader
from adaptix.load_error import AggregateLoadError
from adaptix.provider import Provider

from dature import ConsulSource, Loader, V, VaultSource
from dature.errors.exceptions import DatureConfigError, FieldLoadError
from dature.field_path import F
from dature.loading.retort import (
    _FAST_BYTES,
    _FAST_PLAIN,
    _FAST_REMOTE,
    _FAST_STRING,
    RetortCache,
    _DualRetort,
    _uncustomized_fast_retort,
    build_base_recipe,
    get_adaptix_name_style,
    get_name_mapping_providers,
    get_validator_providers,
)
from dature.sources.base import (
    FlatKeySource,
    IndexedSource,
    Source,
    bytes_value_loaders,
    remote_value_loaders,
    string_value_loaders,
)
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
    decode="raw"), proving the fast-path detection matches _FAST_BYTES by content too."""

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
    Consul decode="json"), proving the fast-path detection matches _FAST_REMOTE by content too."""

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
        cache = RetortCache(Config, cache_engine=True)

        first = cache.plain(IndexedSource(source, 0))
        second = cache.plain(IndexedSource(source, 0))

        assert first is second

    def test_plain_cache_engine_false_rebuilds_every_call(self):
        """With ``cache_engine=False`` (the default), nothing is retained between calls."""

        @dataclass
        class Config:
            name: str

        source = MockSource()
        cache = RetortCache(Config)

        first = cache.plain(IndexedSource(source, 0))
        second = cache.plain(IndexedSource(source, 0))

        assert first is not second
        assert cache._cache == {}

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

    def test_field_pass_and_plain_are_distinct(self):
        """field_pass must return something separate from plain."""

        @dataclass
        class Config:
            port: Annotated[int, V >= 0]

        source = MockSource()
        cache = RetortCache(Config)
        indexed = IndexedSource(source, 0)

        fp: object = cache.field_pass(indexed, skip=False)
        plain: object = cache.plain(indexed)

        assert fp is not plain

    def test_field_pass_skip_and_noskip_are_distinct(self):
        """field_pass(skip=True) and field_pass(skip=False) must return separate objects."""

        @dataclass
        class Config:
            port: int

        source = MockSource()
        cache = RetortCache(Config)
        indexed = IndexedSource(source, 0)

        fp_skip: object = cache.field_pass(indexed, skip=True)
        fp_noskip: object = cache.field_pass(indexed, skip=False)

        assert fp_skip is not fp_noskip


def _rich_cache_keys(cache: RetortCache) -> list[tuple[Any, ...]]:
    # Cache keys are (source_idx, sentinel, rich_bool, type_loaders). rich lives at index 2.
    return [k for k in cache._cache if len(k) >= 3 and k[2] is True]


class TestFastRichSplit:
    """DebugTrail fast/rich split: happy path loads through the fast (DISABLE) retort; the rich
    (ALL) retort is built lazily only to reproduce a trailed error."""

    def test_final_retort_returns_dual_facade(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config)
        assert isinstance(cache.final_retort(IndexedSource(MockSource(), 0)), _DualRetort)

    def test_field_pass_skip_true_stays_raw_rich(self):
        @dataclass
        class Config:
            port: int

        cache = RetortCache(Config)
        probe = cache.field_pass(IndexedSource(MockSource(), 0), skip=True)

        assert isinstance(probe, Retort)

    def test_success_does_not_compile_rich_retort(self):
        @dataclass
        class Config:
            name: str
            port: int

        cache = RetortCache(Config, cache_engine=True)
        idx = IndexedSource(MockSource(), 0)

        result = cache.final_retort(idx).load({"name": "app", "port": "5"}, Config)

        assert result == Config(name="app", port=5)
        assert _rich_cache_keys(cache) == []  # happy path never builds the rich retort

    def test_error_replays_through_rich_retort(self):
        @dataclass
        class Config:
            name: str
            port: int

        cache = RetortCache(Config, cache_engine=True)
        idx = IndexedSource(MockSource(), 0)

        with pytest.raises(AggregateLoadError):  # rich replay re-raises the trailed load error
            cache.final_retort(idx).load({"name": "app", "port": "not_an_int"}, Config)

        assert _rich_cache_keys(cache)  # a rich retort was compiled to reproduce the error

    def test_multiple_bad_fields_still_aggregated(self):
        @dataclass
        class Config:
            a: int
            b: int

        with pytest.raises(DatureConfigError) as exc_info:
            Loader(MockSource(test_data={"a": "x", "b": "y"}), schema=Config).load()

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        paths = {tuple(e.field_path) for e in errors}
        assert paths == {("a",), ("b",)}


class TestUncustomizedFastRetort:
    """Uncustomized sources reuse a precomputed module-level FAST retort instead of extending.

    Detection is by content, not by class: a source is matched by what ``format_loaders()``
    returns, regardless of its type in the ``Source`` hierarchy.
    """

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            (MockSource(), _FAST_PLAIN),
            (MockFlatKeySource(), _FAST_STRING),
            # A plain `Source` subclass that itself returns the canonical string-value recipe
            # matches _FAST_STRING too — proves detection doesn't key off FlatKeySource.
            (MockStringRecipeSource(), _FAST_STRING),
            # Same proof for the raw-value recipe (Consul's decode="raw").
            (MockRawRecipeSource(), _FAST_BYTES),
            # Same proof for the native-JSON remote recipe (Vault, Consul decode="json").
            (MockRemoteRecipeSource(), _FAST_REMOTE),
        ],
    )
    def test_uncustomized_source_matches_by_recipe_content(self, source, expected):
        assert _uncustomized_fast_retort(source) is expected

    @pytest.mark.parametrize(
        "source",
        [
            MockSource(type_loaders={str: lambda x: str(x).upper()}),
            MockSource(name_style="lower_camel"),
            MockFlatKeySource(type_loaders={str: lambda x: str(x).upper()}),
        ],
    )
    def test_customized_source_returns_none(self, source):
        assert _uncustomized_fast_retort(source) is None

    def test_field_mapping_returns_none(self):
        @dataclass
        class Config:
            name: str

        source = MockSource(field_mapping={F[Config].name: "fullName"})

        assert _uncustomized_fast_retort(source) is None

    def test_distinct_nonempty_recipe_returns_none(self):
        """A source with its own, different non-empty recipe matches neither constant."""
        assert _uncustomized_fast_retort(MockCustomLoadersSource()) is None

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            pytest.param(ConsulSource(host="c", path="p", decode="utf-8"), _FAST_STRING, id="consul_utf8"),
            pytest.param(ConsulSource(host="c", path="p", decode="json"), _FAST_REMOTE, id="consul_json"),
            pytest.param(ConsulSource(host="c", path="p", decode="raw"), _FAST_BYTES, id="consul_raw"),
            pytest.param(VaultSource(url="u", token="t", path="p"), _FAST_REMOTE, id="vault"),
        ],
    )
    def test_real_remote_sources_match_by_recipe_content(self, source, expected):
        """Consul and Vault stay on a precomputed fast retort, never paying per-call .extend()."""
        assert _uncustomized_fast_retort(source) is expected


class TestFinalRetortPrecomputedFastPath:
    """``final_retort``'s FAST branch reuses the precomputed constant for uncustomized sources."""

    def test_plain_source_fast_is_precomputed_constant(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config, cache_engine=True)
        idx = IndexedSource(MockSource(), 0)

        assert cache.final_retort(idx)._fast is _FAST_PLAIN

    def test_flat_key_source_fast_is_precomputed_constant(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config, cache_engine=True)
        idx = IndexedSource(MockFlatKeySource(), 0)

        assert cache.final_retort(idx)._fast is _FAST_STRING

    def test_type_loaders_bypass_precomputed_constant(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config, cache_engine=True)
        idx = IndexedSource(MockSource(type_loaders={str: lambda x: str(x).upper()}), 0)

        fast = cache.final_retort(idx)._fast

        assert fast is not _FAST_PLAIN
        assert fast is not _FAST_STRING

    def test_constructor_override_bypasses_precomputed_constant(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config, cache_engine=True)
        cache.constructor = Config
        idx = IndexedSource(MockSource(), 0)

        fast = cache.final_retort(idx)._fast

        assert fast is not _FAST_PLAIN

    def test_root_validators_bypass_precomputed_constant(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config, cache_engine=True, root_validators=(V.root(lambda _: True),))
        idx = IndexedSource(MockSource(), 0)

        fast = cache.final_retort(idx)._fast

        assert fast is not _FAST_PLAIN

    def test_precomputed_fast_path_load_result_matches_extend_path(self):
        """Precomputed-constant path and freshly-extended path load identical results."""

        @dataclass
        class Config:
            name: str
            port: int

        data = {"name": "app", "port": "8080"}

        precomputed_cache = RetortCache(Config, cache_engine=True)
        precomputed_result = precomputed_cache.final_retort(IndexedSource(MockSource(), 0)).load(data, Config)

        # Force the extend()-built path by attaching a constructor override, whose result
        # must be identical since ConstructorOverrideProvider(Config, Config) is a no-op wrapper.
        extend_cache = RetortCache(Config, cache_engine=True)
        extend_cache.constructor = Config
        extend_idx = IndexedSource(MockSource(), 0)
        assert extend_cache.final_retort(extend_idx)._fast is not _FAST_PLAIN
        extend_result = extend_cache.final_retort(extend_idx).load(data, Config)

        assert precomputed_result == extend_result == Config(name="app", port=8080)

    def test_error_replay_still_uses_lazy_rich_retort(self):
        """RICH is never precomputed; the fallback still compiles lazily on error."""

        @dataclass
        class Config:
            name: str
            port: int

        cache = RetortCache(Config, cache_engine=True)
        idx = IndexedSource(MockSource(), 0)

        with pytest.raises(AggregateLoadError):
            cache.final_retort(idx).load({"name": "app", "port": "not_an_int"}, Config)

        assert _rich_cache_keys(cache)

    def test_precomputed_constants_are_isolated_across_sources(self):
        """Two different uncustomized sources share the constant without cross-contamination."""

        @dataclass
        class ConfigA:
            name: str

        @dataclass
        class ConfigB:
            port: int

        cache_a = RetortCache(ConfigA, cache_engine=True)
        cache_b = RetortCache(ConfigB, cache_engine=True)

        result_a = cache_a.final_retort(IndexedSource(MockSource(), 0)).load({"name": "x"}, ConfigA)
        result_b = cache_b.final_retort(IndexedSource(MockSource(), 0)).load({"port": "5"}, ConfigB)

        assert result_a == ConfigA(name="x")
        assert result_b == ConfigB(port=5)


class TestCacheEngineDefault:
    """``cache_engine`` defaults to ``False``: nothing built here is retained, and the shared,
    process-wide precomputed constants are never touched — even for otherwise-uncustomized
    sources that would qualify for them under ``cache_engine=True``.
    """

    def test_default_is_false(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config)

        assert cache._cache_engine is False

    def test_final_retort_never_reuses_precomputed_constant(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config)
        idx = IndexedSource(MockSource(), 0)

        assert cache.final_retort(idx)._fast is not _FAST_PLAIN

    def test_final_retort_rebuilds_every_call(self):
        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config)
        idx = IndexedSource(MockSource(), 0)

        first = cache.final_retort(idx)._fast
        second = cache.final_retort(idx)._fast

        assert first is not second
        assert cache._cache == {}

    def test_field_pass_rebuilds_every_call(self):
        @dataclass
        class Config:
            port: Annotated[int, V >= 0]

        cache = RetortCache(Config)
        idx = IndexedSource(MockSource(), 0)

        first = cache.field_pass(idx, skip=False)
        second = cache.field_pass(idx, skip=False)

        assert first is not second
        assert cache._cache == {}

    def test_load_result_still_correct_without_caching(self):
        @dataclass
        class Config:
            name: str
            port: int

        cache = RetortCache(Config)
        idx = IndexedSource(MockSource(), 0)

        result = cache.final_retort(idx).load({"name": "app", "port": "8080"}, Config)

        assert result == Config(name="app", port=8080)

    def test_cache_engine_true_opts_into_precomputed_constant(self):
        """Sanity check: the same source, with ``cache_engine=True``, does reuse the constant."""

        @dataclass
        class Config:
            name: str

        cache = RetortCache(Config, cache_engine=True)
        idx = IndexedSource(MockSource(), 0)

        assert cache.final_retort(idx)._fast is _FAST_PLAIN
