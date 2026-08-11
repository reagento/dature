"""Tests for backward-compatibility shims (dature._deprecations).

Every shim is scheduled for removal in dature 1.2; these tests pin the
current transitional behavior: the old form still works and emits a
``DeprecationWarning``.
"""

import json
import warnings
from dataclasses import dataclass, fields
from typing import get_args

import pytest
from adaptix import loader
from adaptix.provider import Provider

from dature import EnvSource, configure, load
from dature.cli.parsing import CLI_LOAD_PARAMS, build_load_kwargs_from_dataclass, derive_cli_schema
from dature.config import config
from dature.field_path import F
from dature.loading.loader import Loader
from dature.loading.mask_config import resolve_masking_mode
from dature.sources.base import FileSource
from dature.type_aliases import FileOrStream, JSONValue


@dataclass
class _Config:
    host: str


@dataclass(kw_only=True)
class _LegacyLoaderSource(FileSource):
    """Custom source still overriding the pre-1.0 ``additional_loaders`` hook."""

    format_name: str = "legacy"

    def _load_file(self, path: FileOrStream) -> JSONValue:
        with open(path, encoding="utf-8") as fh:  # noqa: PTH123
            data: JSONValue = json.load(fh)
        return data

    def additional_loaders(self) -> list[Provider]:
        return [loader(str, str.upper)]


def _validate_args_cls() -> type:
    """The ``validate`` subcommand's dataclass, unwrapped from ``| None``."""
    cls = derive_cli_schema()
    validate_field = next(f for f in fields(cls) if f.name == "validate")
    (validate_cls,) = [a for a in get_args(validate_field.type) if a is not type(None)]
    return validate_cls  # type: ignore[no-any-return]


class TestAdditionalLoadersAlias:
    def test_legacy_override_warns_and_still_applies(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"host": "example"}')
        source = _LegacyLoaderSource(file=config_file)

        with pytest.warns(DeprecationWarning, match="additional_loaders"):
            result = load(source, schema=_Config)

        assert result.host == "EXAMPLE"

    def test_new_override_emits_no_warning(self, monkeypatch):
        monkeypatch.setenv("HOST", "example")

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = load(EnvSource(), schema=_Config)

        assert result.host == "example"


class TestSkipInvalidFieldsRename:
    @pytest.mark.parametrize("caller", ["load", "Loader"])
    def test_alias_warns_and_behaves_like_new_param(self, monkeypatch, caller):
        monkeypatch.setenv("HOST", "example")
        source = EnvSource()

        with pytest.warns(DeprecationWarning, match="skip_invalid_fields"):
            result = (
                load(source, schema=_Config, skip_invalid_fields=F.ANY)
                if caller == "load"
                else Loader(source, schema=_Config, skip_invalid_fields=F.ANY).load()
            )

        assert result.host == "example"

    def test_both_old_and_new_raises(self, monkeypatch):
        monkeypatch.setenv("HOST", "example")
        source = EnvSource()

        with pytest.raises(TypeError, match="only one of"):
            load(source, schema=_Config, skip_field_if_invalid=F.ANY, skip_invalid_fields=F.ANY)

    def test_decorator_mode_alias(self, monkeypatch):
        monkeypatch.setenv("HOST", "example")
        source = EnvSource()

        with pytest.warns(DeprecationWarning, match="skip_invalid_fields"):

            @load(source, skip_invalid_fields=F.ANY)
            @dataclass
            class Config:
                host: str

        assert Config().host == "example"


class TestSkipFieldIfInvalidBool:
    @pytest.mark.parametrize(("bool_value", "expected"), [(True, F.ANY), (False, None)])
    def test_load_level_bool_warns_and_normalizes(self, monkeypatch, bool_value, expected):
        monkeypatch.setenv("HOST", "example")
        source = EnvSource()

        with pytest.warns(DeprecationWarning, match="bool"):
            loader_ = Loader(source, schema=_Config, skip_field_if_invalid=bool_value)

        assert loader_._skip_field_if_invalid == expected

    @pytest.mark.parametrize(("bool_value", "expected"), [(True, F.ANY), (False, None)])
    def test_source_level_bool_warns_and_normalizes(self, bool_value, expected):
        with pytest.warns(DeprecationWarning, match="bool"):
            source = EnvSource(skip_field_if_invalid=bool_value)

        assert source.skip_field_if_invalid == expected

    def test_sentinel_value_emits_no_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            source = EnvSource(skip_field_if_invalid=F.ANY)

        assert source.skip_field_if_invalid is F.ANY


def _load_via_load(source):
    return load(source, schema=_Config, mask_secrets=False)


def _load_via_loader(source):
    return Loader(source, schema=_Config, mask_secrets=False).load()


def _load_via_decorator(source):
    @load(source, mask_secrets=False)
    @dataclass
    class Config:
        host: str

    return Config()


class TestMaskSecretsDeprecation:
    @pytest.mark.parametrize(
        "load_fn",
        [_load_via_load, _load_via_loader, _load_via_decorator],
        ids=["load", "Loader", "decorator"],
    )
    def test_alias_warns_and_behaves_like_new_param(self, monkeypatch, load_fn):
        monkeypatch.setenv("HOST", "example")
        source = EnvSource()

        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            result = load_fn(source)

        assert result.host == "example"

    def test_both_old_and_new_masking_mode_wins_no_raise(self, monkeypatch):
        monkeypatch.setenv("HOST", "example")
        source = EnvSource()

        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            loader_ = Loader(source, schema=_Config, mask_secrets=False, masking_mode="secrets_only")

        assert loader_._masking_mode_arg == "secrets_only"

    def test_new_param_alone_emits_no_warning(self, monkeypatch):
        monkeypatch.setenv("HOST", "example")
        source = EnvSource()

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = load(source, schema=_Config, masking_mode="secrets_only")

        assert result.host == "example"

    def test_cli_legacy_flag_warns_and_maps_to_masking_mode(self):
        validate_cls = _validate_args_cls()
        args = validate_cls(
            schema="x:Y",
            source=["type=dature.EnvSource"],
            mask_secrets=True,
        )

        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            kwargs = build_load_kwargs_from_dataclass(args)

        assert kwargs == {"masking_mode": "secrets_only"}

    def test_cli_masking_mode_present_in_derived_schema(self):
        validate_cls = _validate_args_cls()
        names = {f.name for f in fields(validate_cls)}
        assert "masking_mode" in names
        assert "mask_secrets" in names

    @pytest.mark.usefixtures("_reset_config")
    def test_configure_both_set_masking_mode_wins_no_raise(self):
        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            configure(masking={"mask_secrets": False, "masking_mode": "secrets_only"})

        assert config.masking.masking_mode == "secrets_only"
        assert config.masking.mask_secrets is None

    @pytest.mark.usefixtures("_reset_config")
    def test_configure_old_alone_maps_and_warns(self):
        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            configure(masking={"mask_secrets": False})

        assert resolve_masking_mode() == "none"

    @pytest.mark.usefixtures("_reset_config")
    def test_env_both_set_masking_mode_wins_no_raise(self, monkeypatch):
        monkeypatch.setenv("DATURE_MASKING__MASK_SECRETS", "false")
        monkeypatch.setenv("DATURE_MASKING__MASKING_MODE", "secrets_only")

        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            assert config.masking.masking_mode == "secrets_only"
        assert config.masking.mask_secrets is None

    @pytest.mark.usefixtures("_reset_config")
    def test_env_old_alone_maps_and_warns(self, monkeypatch):
        monkeypatch.setenv("DATURE_MASKING__MASK_SECRETS", "false")

        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            resolved = resolve_masking_mode()

        assert resolved == "none"


class TestCliSkipInvalidFieldsFlag:
    def test_legacy_flag_warns_and_maps_to_field_any(self):
        validate_cls = _validate_args_cls()
        args = validate_cls(
            schema="x:Y",
            source=["type=dature.EnvSource"],
            skip_invalid_fields=True,
        )

        with pytest.warns(DeprecationWarning, match="skip-invalid-fields"):
            kwargs = build_load_kwargs_from_dataclass(args)

        assert kwargs == {"skip_field_if_invalid": F.ANY}

    def test_both_old_and_new_flag_raises(self):
        validate_cls = _validate_args_cls()
        args = validate_cls(
            schema="x:Y",
            source=["type=dature.EnvSource"],
            skip_field_if_invalid=True,
            skip_invalid_fields=True,
        )

        with pytest.raises(TypeError, match="only one of"):
            build_load_kwargs_from_dataclass(args)

    def test_no_legacy_flag_emits_no_warning(self):
        validate_cls = _validate_args_cls()
        args = validate_cls(schema="x:Y", source=["type=dature.EnvSource"])

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            kwargs = build_load_kwargs_from_dataclass(args)

        assert kwargs == {}

    def test_flag_present_in_derived_schema(self):
        validate_cls = _validate_args_cls()
        names = {f.name for f in fields(validate_cls)}
        assert "skip_invalid_fields" in names
        assert set(CLI_LOAD_PARAMS) <= names
