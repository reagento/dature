"""Tests for validators/base.py — extract and create validator providers."""

from dataclasses import dataclass
from typing import Annotated

import pytest

from dature.field_path import FieldPath
from dature.validators.base import (
    create_metadata_validator_providers,
    create_root_validator_providers,
    create_validator_providers,
    extract_validators_from_type,
)
from dature.validators.number import Ge, Gt
from dature.validators.root import RootValidator
from dature.validators.string import MinLength


class TestExtractValidatorsFromType:
    def test_plain_type_returns_empty(self):
        result = extract_validators_from_type(str)

        assert result == []

    def test_annotated_without_validators_returns_empty(self):
        result = extract_validators_from_type(Annotated[int, "some metadata"])

        assert result == []

    def test_annotated_with_validator(self):
        result = extract_validators_from_type(Annotated[str, MinLength(3)])

        assert len(result) == 1
        assert isinstance(result[0], MinLength)

    def test_annotated_with_multiple_validators(self):
        result = extract_validators_from_type(Annotated[int, Gt(0), Ge(0)])

        assert len(result) == 2

    def test_annotated_mixed_metadata_and_validators(self):
        result = extract_validators_from_type(Annotated[str, "description", MinLength(1)])

        assert len(result) == 1
        assert isinstance(result[0], MinLength)


class TestCreateValidatorProviders:
    def test_creates_providers_from_validators(self):
        @dataclass
        class Cfg:
            name: str

        validators = [MinLength(3)]
        result = create_validator_providers(Cfg, "name", validators)

        assert len(result) == 1


class TestCreateMetadataValidatorProviders:
    def test_single_field_validator(self):
        @dataclass
        class Cfg:
            name: str

        fp = FieldPath(owner=Cfg, parts=("name",))
        result = create_metadata_validator_providers({fp: MinLength(3)})

        assert len(result) == 1

    def test_tuple_validators(self):
        @dataclass
        class Cfg:
            value: int

        fp = FieldPath(owner=Cfg, parts=("value",))
        result = create_metadata_validator_providers({fp: (Gt(0), Ge(0))})

        assert len(result) == 2

    def test_empty_field_path_raises(self):
        @dataclass
        class Cfg:
            name: str

        fp = FieldPath(owner=Cfg, parts=())

        with pytest.raises(ValueError, match="FieldPath must contain at least one field name"):
            create_metadata_validator_providers({fp: MinLength(3)})

    @pytest.mark.parametrize(
        "parts",
        [("name",), ("inner", "name")],
        ids=["single", "nested"],
    )
    def test_string_owner_raises(self, parts: tuple[str, ...]):
        fp = FieldPath(owner="Cfg", parts=parts)

        with pytest.raises(TypeError, match="string owner"):
            create_metadata_validator_providers({fp: MinLength(3)})

    def test_non_fieldpath_key_raises(self):
        with pytest.raises(TypeError, match="validators key must be a FieldPath"):
            create_metadata_validator_providers({"name": MinLength(3)})

    def test_nested_field_path(self):
        @dataclass
        class Inner:
            value: str

        @dataclass
        class Outer:
            inner: Inner

        fp = FieldPath(owner=Outer, parts=("inner", "value"))
        result = create_metadata_validator_providers({fp: MinLength(1)})

        assert len(result) == 1


class TestCreateRootValidatorProviders:
    def test_creates_providers(self):
        @dataclass
        class Cfg:
            name: str

        rv = RootValidator(func=lambda _self: True)
        result = create_root_validator_providers(Cfg, (rv,))

        assert len(result) == 1

    def test_multiple_root_validators(self):
        @dataclass
        class Cfg:
            name: str

        rv1 = RootValidator(func=lambda _self: True)
        rv2 = RootValidator(func=lambda _self: True, error_message="custom")
        result = create_root_validator_providers(Cfg, (rv1, rv2))

        assert len(result) == 2
