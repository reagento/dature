"""Tests for providers/model.py."""

from dataclasses import dataclass, field
from typing import Any

import pytest
from adaptix import NameStyle, Provider, Retort, name_mapping
from adaptix.load_error import LoadError

from dature.providers.model import ImplicitNestedDefaultProvider, RequireUnsafeFactoryFieldsProvider


@dataclass
class _Inner:
    a: int
    b: int


@dataclass
class _FactoryConfig:
    inner: _Inner = field(default_factory=_Inner)


@dataclass(frozen=True, kw_only=True, slots=True)
class _Cors:
    allow_origins: tuple[str, ...] = ("http://localhost",)
    allow_credentials: bool = True


@dataclass
class _WithCors:
    cors: _Cors


@dataclass
class _WithRequiredNested:
    inner: _Inner


@dataclass
class _Address:
    city: str = "Paris"


@dataclass
class _User:
    address: _Address


@dataclass
class _Leaf:
    value: int = 1


@dataclass
class _Mid:
    leaf: _Leaf


@dataclass
class _TwoLevels:
    mid: _Mid


@dataclass
class _ChainWithRequired:
    inner: _WithRequiredNested


@dataclass
class _SelfRef:
    child: "_SelfRef"


@pytest.fixture
def factory_retort() -> Retort:
    return Retort(recipe=[RequireUnsafeFactoryFieldsProvider()])


class TestRequireUnsafeFactoryFieldsProvider:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({"inner": {"a": 1, "b": 2}}, _FactoryConfig(inner=_Inner(a=1, b=2))),
        ],
    )
    def test_unsafe_factory_field_loads_when_present(
        self,
        factory_retort: Retort,
        data: dict[str, Any],
        expected: _FactoryConfig,
    ):
        result = factory_retort.load(data, _FactoryConfig)

        assert result == expected

    def test_unsafe_factory_field_becomes_required(self, factory_retort: Retort):
        with pytest.raises(LoadError):
            factory_retort.load({}, _FactoryConfig)

    def test_safe_factory_schema_passes_through_to_default_recipe(self, factory_retort: Retort):
        @dataclass
        class Config:
            items: list[int] = field(default_factory=list)

        result = factory_retort.load({}, Config)

        assert result == Config(items=[])

    def test_optional_field_before_unsafe_factory_field_still_loads(self, factory_retort: Retort):
        @dataclass
        class Config:
            debug: bool = False
            inner: _Inner = field(default_factory=_Inner)

        result = factory_retort.load({"debug": True, "inner": {"a": 1, "b": 2}}, Config)

        assert result == Config(debug=True, inner=_Inner(a=1, b=2))


class TestImplicitNestedDefaultProvider:
    @pytest.fixture
    def retort(self) -> Retort:
        return Retort(recipe=[ImplicitNestedDefaultProvider()])

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({}, _WithCors(cors=_Cors())),
            ({"cors": {}}, _WithCors(cors=_Cors())),
            ({"cors": {"allow_credentials": False}}, _WithCors(cors=_Cors(allow_credentials=False))),
        ],
        ids=["absent", "empty_dict", "partial"],
    )
    def test_nested_all_defaults_is_optional(self, retort: Retort, data: dict[str, Any], expected: _WithCors):
        result = retort.load(data, _WithCors)

        assert result == expected

    def test_nested_with_required_field_stays_required(self, retort: Retort):
        with pytest.raises(LoadError):
            retort.load({}, _WithRequiredNested)

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({}, _TwoLevels(mid=_Mid(leaf=_Leaf()))),
            ({"mid": {}}, _TwoLevels(mid=_Mid(leaf=_Leaf()))),
            ({"mid": {"leaf": {"value": 5}}}, _TwoLevels(mid=_Mid(leaf=_Leaf(value=5)))),
        ],
        ids=["absent", "empty_dict", "partial"],
    )
    def test_recursive_nested_defaults(self, retort: Retort, data: dict[str, Any], expected: _TwoLevels):
        result = retort.load(data, _TwoLevels)

        assert result == expected

    def test_recursive_chain_with_required_leaf_stays_required(self, retort: Retort):
        with pytest.raises(LoadError):
            retort.load({}, _ChainWithRequired)

    def test_self_referential_schema_does_not_loop(self, retort: Retort):
        with pytest.raises(LoadError):
            retort.load({}, _SelfRef)

    def test_optional_field_before_nested_loads(self, retort: Retort):
        @dataclass(kw_only=True)
        class Config:
            debug: bool = False
            cors: _Cors

        result = retort.load({}, Config)

        assert result == Config(debug=False, cors=_Cors())

    @pytest.mark.parametrize(
        ("mapping", "data"),
        [
            (name_mapping(name_style=NameStyle.UPPER_SNAKE), {"ADDRESS": {"CITY": "Rome"}}),
            (name_mapping(map={"address": "location"}), {"location": {"city": "Rome"}}),
        ],
        ids=["name_style", "alias"],
    )
    def test_absent_field_name_does_not_shadow_alias(self, mapping: Provider, data: dict[str, Any]):
        retort = Retort(recipe=[ImplicitNestedDefaultProvider(), mapping])

        result = retort.load(data, _User)

        assert result == _User(address=_Address(city="Rome"))

    def test_alias_absent_falls_back_to_defaults(self):
        retort = Retort(recipe=[ImplicitNestedDefaultProvider(), name_mapping(map={"address": "location"})])

        result = retort.load({}, _User)

        assert result == _User(address=_Address())
