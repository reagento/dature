"""Tests for validators/base.py — extract and create validator providers."""

from dataclasses import dataclass
from typing import Annotated

import pytest

from dature import V
from dature.errors import ValidatorTypeError
from dature.field_path import FieldPath
from dature.validators.base import (
    create_metadata_validator_providers,
    create_root_validator_providers,
    create_validator_providers,
    extract_and_check_validators,
)


class TestExtractAndCheckValidators:
    def test_plain_type_returns_empty(self):
        assert extract_and_check_validators(str, field_path=["x"]) == []

    def test_annotated_without_validators_returns_empty(self):
        assert extract_and_check_validators(Annotated[int, "some metadata"], field_path=["x"]) == []

    def test_annotated_with_validator(self):
        result = extract_and_check_validators(Annotated[str, V.len() >= 3], field_path=["x"])

        assert len(result) == 1

    def test_annotated_mixed_metadata_and_validators(self):
        result = extract_and_check_validators(
            Annotated[str, "description", V.len() >= 1],
            field_path=["x"],
        )

        assert len(result) == 1

    def test_annotated_with_and_is_flattened(self):
        result = extract_and_check_validators(
            Annotated[int, (V > 0) & (V < 100)],
            field_path=["x"],
        )

        assert len(result) == 2

    def test_annotated_with_legacy_tuple_style_still_supported(self):
        # Two separate predicates act like an implicit AND.
        result = extract_and_check_validators(
            Annotated[int, V > 0, V < 100],
            field_path=["x"],
        )

        assert len(result) == 2

    def test_incompatible_type_raises(self):
        with pytest.raises(ValidatorTypeError, match=r"V\.len\(\)"):
            extract_and_check_validators(Annotated[int, V.len() >= 3], field_path=["port"])

    def test_root_predicate_in_annotated_raises(self):
        with pytest.raises(TypeError, match=r"source\.root_validators"):
            extract_and_check_validators(
                Annotated[int, V.root(lambda _: True)],
                field_path=["port"],
            )


class TestCreateValidatorProviders:
    def test_creates_provider_per_predicate(self):
        @dataclass
        class Cfg:
            name: str

        predicates = [V.len() >= 3]
        result = create_validator_providers(Cfg, "name", predicates)

        assert len(result) == 1


class TestCreateMetadataValidatorProviders:
    def test_single_field_validator(self):
        @dataclass
        class Cfg:
            name: str

        fp = FieldPath(owner=Cfg, parts=("name",))
        result = create_metadata_validator_providers({fp: V.len() >= 3})

        assert len(result) == 1

    def test_tuple_validators(self):
        @dataclass
        class Cfg:
            value: int

        fp = FieldPath(owner=Cfg, parts=("value",))
        result = create_metadata_validator_providers({fp: (V > 0, V >= 0)})

        assert len(result) == 2

    def test_and_composition_flattens(self):
        @dataclass
        class Cfg:
            value: int

        fp = FieldPath(owner=Cfg, parts=("value",))
        result = create_metadata_validator_providers({fp: (V > 0) & (V < 100)})

        assert len(result) == 2

    def test_empty_field_path_raises(self):
        @dataclass
        class Cfg:
            name: str

        fp = FieldPath(owner=Cfg, parts=())

        with pytest.raises(ValueError, match="FieldPath must contain at least one field name"):
            create_metadata_validator_providers({fp: V.len() >= 3})

    @pytest.mark.parametrize(
        "parts",
        [("name",), ("inner", "name")],
        ids=["single", "nested"],
    )
    def test_string_owner_raises(self, parts: tuple[str, ...]):
        fp = FieldPath(owner="Cfg", parts=parts)

        with pytest.raises(TypeError, match="string owner"):
            create_metadata_validator_providers({fp: V.len() >= 3})

    def test_non_fieldpath_key_raises(self):
        with pytest.raises(TypeError, match="validators key must be a FieldPath"):
            create_metadata_validator_providers({"name": V.len() >= 3})

    def test_nested_field_path(self):
        @dataclass
        class Inner:
            value: str

        @dataclass
        class Outer:
            inner: Inner

        fp = FieldPath(owner=Outer, parts=("inner", "value"))
        result = create_metadata_validator_providers({fp: V.len() >= 1})

        assert len(result) == 1

    def test_root_predicate_rejected(self):
        @dataclass
        class Cfg:
            name: str

        fp = FieldPath(owner=Cfg, parts=("name",))

        with pytest.raises(TypeError, match=r"source\.root_validators"):
            create_metadata_validator_providers({fp: V.root(lambda _: True)})  # type: ignore[dict-item]

    def test_non_predicate_value_rejected(self):
        @dataclass
        class Cfg:
            name: str

        fp = FieldPath(owner=Cfg, parts=("name",))

        with pytest.raises(TypeError, match="must be a V-predicate"):
            create_metadata_validator_providers({fp: "not a predicate"})  # type: ignore[dict-item]

    def test_incompatible_type_raises(self):
        @dataclass
        class Cfg:
            port: int

        fp = FieldPath(owner=Cfg, parts=("port",))

        with pytest.raises(ValidatorTypeError, match=r"V\.len\(\)"):
            create_metadata_validator_providers({fp: V.len() >= 3})


class TestCreateRootValidatorProviders:
    def test_creates_providers(self):
        @dataclass
        class Cfg:
            name: str

        rp = V.root(lambda _self: True)
        result = create_root_validator_providers(Cfg, (rp,))

        assert len(result) == 1

    def test_multiple_root_validators(self):
        @dataclass
        class Cfg:
            name: str

        rp1 = V.root(lambda _self: True)
        rp2 = V.root(lambda _self: True, error_message="custom")
        result = create_root_validator_providers(Cfg, (rp1, rp2))

        assert len(result) == 2
