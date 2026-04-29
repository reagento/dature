"""Tests for FieldPath lazy field path builder."""

from dataclasses import dataclass

import pytest

from dature.field_path import F, FieldPath, extract_field_path, validate_field_path_owner


@dataclass
class _Database:
    uri: str


@dataclass
class _Cfg:
    host: str
    database: _Database


class TestFieldPath:
    @pytest.mark.parametrize(
        ("field_path", "expected_path"),
        [
            pytest.param(F[_Cfg].host, "host", id="single_field_class"),
            pytest.param(F[_Cfg].database.uri, "database.uri", id="nested_field_class"),
            pytest.param(F["Config"].host, "host", id="single_field_string"),
            pytest.param(F["Config"].database.uri, "database.uri", id="nested_field_string"),
        ],
    )
    def test_path(self, field_path: FieldPath, expected_path: str):
        assert field_path.as_path() == expected_path

    def test_owner_is_class(self):
        assert F[_Cfg].host.owner is _Cfg

    def test_owner_is_string(self):
        assert F["Config"].host.owner == "Config"

    def test_no_fields_raises_value_error(self):
        with pytest.raises(ValueError, match="at least one field name"):
            F[_Cfg].as_path()

    def test_is_frozen(self):
        fp = F[_Cfg].host
        with pytest.raises(AttributeError):
            fp.owner = "other"

    def test_nonexistent_field_raises_attribute_error(self):
        with pytest.raises(AttributeError, match="'_Cfg' has no field 'nonexistent'"):
            _ = F[_Cfg].nonexistent

    def test_not_a_dataclass_raises_type_error(self):
        class Plain:
            pass

        with pytest.raises(TypeError, match="'Plain' is not a dataclass"):
            F[Plain]

    def test_string_owner_skips_validation(self):
        fp = F["Whatever"].anything.deep.path
        assert fp.as_path() == "anything.deep.path"


class TestValidateFieldPathOwner:
    def test_string_owner_matches(self):
        validate_field_path_owner(F["_Cfg"].host, _Cfg)

    def test_type_owner_matches(self):
        validate_field_path_owner(F[_Cfg].host, _Cfg)

    def test_string_owner_mismatch(self):
        with pytest.raises(TypeError) as exc_info:
            validate_field_path_owner(F["Other"].host, _Cfg)
        assert str(exc_info.value) == "FieldPath owner 'Other' does not match target dataclass '_Cfg'"

    def test_type_owner_mismatch(self):
        with pytest.raises(TypeError) as exc_info:
            validate_field_path_owner(F[_Database].uri, _Cfg)
        assert str(exc_info.value) == "FieldPath owner '_Database' does not match target dataclass '_Cfg'"

    def test_string_owner_nonexistent_field(self):
        with pytest.raises(AttributeError, match="'_Cfg' has no field 'nonexistent'"):
            validate_field_path_owner(F["_Cfg"].nonexistent, _Cfg)

    def test_string_owner_nonexistent_nested_field(self):
        with pytest.raises(AttributeError, match="'_Database' has no field 'missing'"):
            validate_field_path_owner(F["_Cfg"].database.missing, _Cfg)

    def test_string_owner_valid_nested_path(self):
        validate_field_path_owner(F["_Cfg"].database.uri, _Cfg)


class TestExtractFieldPath:
    @pytest.mark.parametrize(
        ("field_path", "expected"),
        [
            pytest.param(F[_Cfg].host, "host", id="single_field"),
            pytest.param(F[_Cfg].database.uri, "database.uri", id="nested_field"),
        ],
    )
    def test_path(self, field_path: FieldPath, expected: str):
        assert extract_field_path(field_path) == expected

    def test_no_fields_raises_value_error(self):
        with pytest.raises(ValueError, match="at least one field name"):
            extract_field_path(F[_Cfg])

    def test_validates_owner_mismatch(self):
        with pytest.raises(TypeError) as exc_info:
            extract_field_path(F["Other"].host, schema=_Cfg)
        assert str(exc_info.value) == "FieldPath owner 'Other' does not match target dataclass '_Cfg'"

    def test_passes_with_correct_string_owner(self):
        assert extract_field_path(F["_Cfg"].host, schema=_Cfg) == "host"
