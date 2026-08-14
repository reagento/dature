"""Tests for backward-compatibility shims (dature._deprecations).

``mask_secrets`` is scheduled for removal in dature 1.3; these tests pin the
current transitional behavior: the old form still works and emits a
``DeprecationWarning``.
"""

import warnings
from dataclasses import dataclass, fields
from typing import get_args

import pytest

from dature import EnvSource, configure, load
from dature.cli.parsing import build_load_kwargs_from_dataclass, derive_cli_schema
from dature.config import config
from dature.loading.loader import Loader
from dature.loading.mask_config import resolve_masking_mode


@dataclass
class _Config:
    host: str


def _validate_args_cls() -> type:
    """The ``validate`` subcommand's dataclass, unwrapped from ``| None``."""
    cls = derive_cli_schema()
    validate_field = next(f for f in fields(cls) if f.name == "validate")
    (validate_cls,) = [a for a in get_args(validate_field.type) if a is not type(None)]
    return validate_cls  # type: ignore[no-any-return]


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
