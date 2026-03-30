from typing import Any

import pytest

from dature.config import (
    ErrorDisplayConfig,
    LoadingConfig,
    MaskingConfig,
    _ConfigProxy,
    config,
    configure,
)
from dature.errors.exceptions import DatureConfigError


@pytest.mark.usefixtures("_reset_config")
class TestConfigProxy:
    @staticmethod
    def test_proxy_caches_instance() -> None:
        first = config.ensure_loaded()
        second = config.ensure_loaded()
        assert first is second


@pytest.mark.usefixtures("_reset_config")
class TestConfigure:
    @staticmethod
    @pytest.mark.parametrize(
        ("kwargs", "attr_path", "expected"),
        [
            (
                {"masking": {"mask": "[HIDDEN]"}},
                ("masking", "mask"),
                "[HIDDEN]",
            ),
            (
                {"masking": {"visible_prefix": 3}},
                ("masking", "visible_prefix"),
                3,
            ),
            (
                {"error_display": {"max_visible_lines": 10}},
                ("error_display", "max_visible_lines"),
                10,
            ),
            (
                {"loading": {"cache": False, "debug": True}},
                ("loading", "cache"),
                False,
            ),
            (
                {"loading": {"cache": False, "debug": True}},
                ("loading", "debug"),
                True,
            ),
        ],
        ids=[
            "masking-mask",
            "masking-visible_prefix",
            "error_display-max_visible_lines",
            "loading-cache",
            "loading-debug",
        ],
    )
    def test_configure_overrides(
        kwargs: dict[str, Any],
        attr_path: tuple[str, str],
        expected: str | int | bool,
    ) -> None:
        configure(**kwargs)
        group = getattr(config, attr_path[0])
        assert getattr(group, attr_path[1]) == expected

    @staticmethod
    @pytest.mark.parametrize(
        ("kwargs", "unchanged_group", "expected_default"),
        [
            (
                {"masking": {"mask": "###"}},
                "error_display",
                ErrorDisplayConfig(),
            ),
            (
                {"masking": {"mask": "###"}},
                "loading",
                LoadingConfig(),
            ),
            (
                {"error_display": {"max_visible_lines": 10}},
                "masking",
                MaskingConfig(),
            ),
        ],
        ids=[
            "masking-preserves-error_display",
            "masking-preserves-loading",
            "error_display-preserves-masking",
        ],
    )
    def test_configure_preserves_other_groups(
        kwargs: dict[str, Any],
        unchanged_group: str,
        expected_default: MaskingConfig | ErrorDisplayConfig | LoadingConfig,
    ) -> None:
        configure(**kwargs)
        assert getattr(config, unchanged_group) == expected_default


@pytest.mark.usefixtures("_reset_config")
class TestEnvLoading:
    @staticmethod
    @pytest.mark.parametrize(
        ("env_var", "env_value", "attr_path", "expected"),
        [
            (
                "DATURE_MASKING__MASK",
                "[HIDDEN]",
                ("masking", "mask"),
                "[HIDDEN]",
            ),
            (
                "DATURE_MASKING__VISIBLE_PREFIX",
                "4",
                ("masking", "visible_prefix"),
                4,
            ),
            (
                "DATURE_LOADING__CACHE",
                "false",
                ("loading", "cache"),
                False,
            ),
            (
                "DATURE_LOADING__DEBUG",
                "true",
                ("loading", "debug"),
                True,
            ),
            (
                "DATURE_MASKING__MASK_SECRETS",
                "false",
                ("masking", "mask_secrets"),
                False,
            ),
            (
                "DATURE_MASKING__SECRET_FIELD_NAMES",
                '["password","token","secret"]',
                ("masking", "secret_field_names"),
                ("password", "token", "secret"),
            ),
        ],
        ids=[
            "str-mask",
            "int-visible_prefix",
            "bool-cache-false",
            "bool-debug-true",
            "bool-mask_secrets-false",
            "tuple-secret_field_names",
        ],
    )
    def test_env_loading(
        monkeypatch: pytest.MonkeyPatch,
        env_var: str,
        env_value: str,
        attr_path: tuple[str, str],
        expected: str | int | bool | tuple[str, ...],
    ) -> None:
        monkeypatch.setenv(env_var, env_value)
        _ConfigProxy.set_instance(None)
        group = getattr(config, attr_path[0])
        assert getattr(group, attr_path[1]) == expected


@pytest.mark.usefixtures("_reset_config")
class TestValidation:
    @staticmethod
    @pytest.mark.parametrize(
        ("env_var", "env_value", "attr"),
        [
            ("DATURE_MASKING__MASK", "", "masking"),
            ("DATURE_MASKING__VISIBLE_PREFIX", "-1", "masking"),
            ("DATURE_ERROR_DISPLAY__MAX_VISIBLE_LINES", "0", "error_display"),
        ],
        ids=[
            "empty-mask",
            "negative-visible_prefix",
            "zero-max_visible_lines",
        ],
    )
    def test_invalid_env_raises(
        monkeypatch: pytest.MonkeyPatch,
        env_var: str,
        env_value: str,
        attr: str,
    ) -> None:
        monkeypatch.setenv(env_var, env_value)
        _ConfigProxy.set_instance(None)
        with pytest.raises(DatureConfigError):
            _ = getattr(config, attr)
