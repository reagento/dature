import threading
from dataclasses import dataclass, field
from typing import Any

import pytest

import dature
from dature.config import (
    ErrorDisplayConfig,
    LoadingConfig,
    MaskingConfig,
    configure,
    default_config,
    merge_group,
    resolve_config,
    resolve_error_display,
)
from dature.errors import DatureConfigError
from dature.instance import Dature
from dature.loading.loader import Loader
from dature.masking.detection import build_secret_paths


@dataclass
class _SampleDC:
    x: str = "default"


@pytest.mark.usefixtures("_reset_config")
class TestDefaultConfig:
    @staticmethod
    def test_default_config_caches() -> None:
        """default_config() is memoized — two calls return the same object."""
        first = default_config()
        second = default_config()
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
            (
                {"loading": {"cache_engine": True}},
                ("loading", "cache_engine"),
                True,
            ),
            (
                {"loading": {"stale_on_error": "raise"}},
                ("loading", "stale_on_error"),
                "raise",
            ),
            (
                {"loading": {"search_system_paths": False}},
                ("loading", "search_system_paths"),
                False,
            ),
            (
                {"vault": {"host": "vault.internal"}},
                ("vault", "host"),
                "vault.internal",
            ),
            (
                {"consul": {"datacenter": "dc1"}},
                ("consul", "datacenter"),
                "dc1",
            ),
            (
                {"etcd": {"user": "admin"}},
                ("etcd", "user"),
                "admin",
            ),
            (
                {"ssm": {"region_name": "eu-west-1"}},
                ("ssm", "region_name"),
                "eu-west-1",
            ),
            (
                {"secrets_manager": {"region_name": "eu-west-1"}},
                ("secrets_manager", "region_name"),
                "eu-west-1",
            ),
            (
                {"azure_app_config": {"endpoint": "https://x.azconfig.io"}},
                ("azure_app_config", "endpoint"),
                "https://x.azconfig.io",
            ),
            (
                {"azure_key_vault": {"vault_url": "https://x.vault.azure.net"}},
                ("azure_key_vault", "vault_url"),
                "https://x.vault.azure.net",
            ),
            (
                {"gcp_secret_manager": {"project_id": "my-proj"}},
                ("gcp_secret_manager", "project_id"),
                "my-proj",
            ),
        ],
        ids=[
            "masking-mask",
            "masking-visible_prefix",
            "error_display-max_visible_lines",
            "loading-cache",
            "loading-debug",
            "loading-cache_engine",
            "loading-stale_on_error",
            "loading-search_system_paths",
            "vault-host",
            "consul-datacenter",
            "etcd-user",
            "ssm-region_name",
            "secrets_manager-region_name",
            "azure_app_config-endpoint",
            "azure_key_vault-vault_url",
            "gcp_secret_manager-project_id",
        ],
    )
    def test_configure_overrides(
        kwargs: dict[str, Any],
        attr_path: tuple[str, str],
        expected: str | int | bool,
    ) -> None:
        with pytest.warns(DeprecationWarning, match="configure()"):
            configure(**kwargs)

        group = getattr(resolve_config(), attr_path[0])
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
        with pytest.warns(DeprecationWarning, match="configure()"):
            configure(**kwargs)
        assert getattr(resolve_config(), unchanged_group) == expected_default

    @staticmethod
    def test_configure_issues_deprecation_warning() -> None:
        """configure() must emit a DeprecationWarning pointing at dature 1.5."""
        with pytest.warns(DeprecationWarning, match="1.5"):
            configure(masking={"mask": "[GONE]"})


@pytest.mark.usefixtures("_reset_config")
class TestConfigureEmptyDictReset:
    @staticmethod
    @pytest.mark.parametrize(
        ("group", "override", "expected_default"),
        [
            (
                "masking",
                {"mask": "*****", "visible_prefix": 2, "visible_suffix": 2},
                MaskingConfig(),
            ),
            (
                "error_display",
                {"max_visible_lines": 10, "max_line_length": 200},
                ErrorDisplayConfig(),
            ),
            (
                "loading",
                {"cache": False, "debug": True},
                LoadingConfig(),
            ),
        ],
        ids=["masking", "error_display", "loading"],
    )
    def test_empty_dict_resets_group_to_defaults(
        group: str,
        override: dict[str, Any],
        expected_default: MaskingConfig | ErrorDisplayConfig | LoadingConfig,
    ) -> None:
        with pytest.warns(DeprecationWarning, match="configure()"):
            configure(**{group: override})
        assert getattr(resolve_config(), group) != expected_default

        with pytest.warns(DeprecationWarning, match="configure()"):
            configure(**{group: {}})
        assert getattr(resolve_config(), group) == expected_default

    @staticmethod
    def test_empty_dict_preserves_other_groups() -> None:
        with pytest.warns(DeprecationWarning, match="configure()"):
            configure(masking={"mask": "*****"}, error_display={"max_visible_lines": 10})
        with pytest.warns(DeprecationWarning, match="configure()"):
            configure(masking={})

        assert resolve_config().masking == MaskingConfig()
        assert resolve_config().error_display.max_visible_lines == 10

    @staticmethod
    def test_concurrent_configure_calls_do_not_lose_groups() -> None:
        """Two concurrent configure() calls updating different groups must both take effect."""
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def call_masking() -> None:
            try:
                barrier.wait()
                with pytest.warns(DeprecationWarning, match="configure()"):
                    configure(masking={"mask": "[SECRET]"})
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def call_loading() -> None:
            try:
                barrier.wait()
                with pytest.warns(DeprecationWarning, match="configure()"):
                    configure(loading={"debug": True})
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=call_masking)
        t2 = threading.Thread(target=call_loading)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        cfg = resolve_config()
        assert cfg.masking.mask == "[SECRET]"
        assert cfg.loading.debug is True


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
                "DATURE_LOADING__STALE_ON_ERROR",
                "retry",
                ("loading", "stale_on_error"),
                "retry",
            ),
            (
                "DATURE_MASKING__SECRET_FIELD_NAMES",
                '["password","token","secret"]',
                ("masking", "secret_field_names"),
                ("password", "token", "secret"),
            ),
            (
                "DATURE_ERROR_DISPLAY__MAX_LINE_LENGTH",
                "120",
                ("error_display", "max_line_length"),
                120,
            ),
            (
                "DATURE_VAULT__HOST",
                "vault.internal",
                ("vault", "host"),
                "vault.internal",
            ),
            (
                "DATURE_CONSUL__DATACENTER",
                "dc1",
                ("consul", "datacenter"),
                "dc1",
            ),
            (
                "DATURE_ETCD__USER",
                "admin",
                ("etcd", "user"),
                "admin",
            ),
            (
                "DATURE_SSM__REGION_NAME",
                "eu-west-1",
                ("ssm", "region_name"),
                "eu-west-1",
            ),
            (
                "DATURE_SECRETS_MANAGER__REGION_NAME",
                "eu-west-1",
                ("secrets_manager", "region_name"),
                "eu-west-1",
            ),
            (
                "DATURE_AZURE_APP_CONFIG__ENDPOINT",
                "https://x.azconfig.io",
                ("azure_app_config", "endpoint"),
                "https://x.azconfig.io",
            ),
            (
                "DATURE_AZURE_KEY_VAULT__VAULT_URL",
                "https://x.vault.azure.net",
                ("azure_key_vault", "vault_url"),
                "https://x.vault.azure.net",
            ),
            (
                "DATURE_GCP_SECRET_MANAGER__PROJECT_ID",
                "my-proj",
                ("gcp_secret_manager", "project_id"),
                "my-proj",
            ),
        ],
        ids=[
            "str-mask",
            "int-visible_prefix",
            "bool-cache-false",
            "bool-debug-true",
            "literal-stale_on_error-retry",
            "tuple-secret_field_names",
            "int-error_display-max_line_length",
            "str-vault-host",
            "str-consul-datacenter",
            "str-etcd-user",
            "str-ssm-region_name",
            "str-secrets_manager-region_name",
            "str-azure_app_config-endpoint",
            "str-azure_key_vault-vault_url",
            "str-gcp_secret_manager-project_id",
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
        default_config.cache_clear()

        group = getattr(default_config(), attr_path[0])

        assert getattr(group, attr_path[1]) == expected


@pytest.mark.usefixtures("_reset_config")
class TestConcurrentDefaultConfig:
    @staticmethod
    def test_concurrent_default_config_consistent() -> None:
        """Multiple threads calling default_config() get equal (not necessarily identical) results."""
        results: list[MaskingConfig] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                results.append(default_config().masking)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(r == results[0] for r in results)


@pytest.mark.usefixtures("_reset_config")
class TestDatureInstance:
    @staticmethod
    @pytest.mark.parametrize(
        ("kwargs", "attr_path", "expected"),
        [
            ({"masking": {"mask": "[HIDDEN]"}}, ("masking", "mask"), "[HIDDEN]"),
            (
                {"error_display": {"max_visible_lines": 10}},
                ("error_display", "max_visible_lines"),
                10,
            ),
            ({"loading": {"debug": True}}, ("loading", "debug"), True),
            ({"vault": {"host": "vault.internal"}}, ("vault", "host"), "vault.internal"),
            ({"consul": {"datacenter": "dc1"}}, ("consul", "datacenter"), "dc1"),
            ({"etcd": {"user": "admin"}}, ("etcd", "user"), "admin"),
            ({"ssm": {"region_name": "eu-west-1"}}, ("ssm", "region_name"), "eu-west-1"),
            (
                {"secrets_manager": {"region_name": "eu-west-1"}},
                ("secrets_manager", "region_name"),
                "eu-west-1",
            ),
            (
                {"azure_app_config": {"endpoint": "https://x.azconfig.io"}},
                ("azure_app_config", "endpoint"),
                "https://x.azconfig.io",
            ),
            (
                {"azure_key_vault": {"vault_url": "https://x.vault.azure.net"}},
                ("azure_key_vault", "vault_url"),
                "https://x.vault.azure.net",
            ),
            (
                {"gcp_secret_manager": {"project_id": "my-proj"}},
                ("gcp_secret_manager", "project_id"),
                "my-proj",
            ),
        ],
        ids=[
            "masking-mask",
            "error_display-max_visible_lines",
            "loading-debug",
            "vault-host",
            "consul-datacenter",
            "etcd-user",
            "ssm-region_name",
            "secrets_manager-region_name",
            "azure_app_config-endpoint",
            "azure_key_vault-vault_url",
            "gcp_secret_manager-project_id",
        ],
    )
    def test_dature_instance_group_overrides(
        kwargs: dict[str, Any],
        attr_path: tuple[str, str],
        expected: str | int | bool,
    ) -> None:
        app = Dature(**kwargs)
        group = getattr(app.config, attr_path[0])
        assert getattr(group, attr_path[1]) == expected

    @staticmethod
    def test_dature_instances_independent() -> None:
        a = Dature(masking={"mask": "AAA"})
        b = Dature(masking={"mask": "BBB"})
        assert a.config.masking.mask == "AAA"
        assert b.config.masking.mask == "BBB"

    @staticmethod
    def test_dature_inherits_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATURE_LOADING__DEBUG", "true")
        default_config.cache_clear()
        app = Dature()
        assert app.config.loading.debug is True

    @staticmethod
    def test_two_instances_independent_in_threads() -> None:
        """Two Dature instances with different vault.host are independent across threads."""
        a = Dature(vault={"host": "host-a"})
        b = Dature(vault={"host": "host-b"})
        results: list[tuple[str, str]] = []
        errors: list[Exception] = []

        def worker(instance: Dature, label: str) -> None:
            try:
                results.append((label, instance.config.vault.host))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(a, "a")),
            threading.Thread(target=worker, args=(b, "b")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        by_label = dict(results)
        assert by_label["a"] == "host-a"
        assert by_label["b"] == "host-b"

    @staticmethod
    def test_default_config_not_called_when_loader_config_explicit() -> None:
        """Passing config= to Loader bypasses resolve_config() / default_config()."""
        app = Dature(masking={"mask": "[TEST]"})
        before = default_config.cache_info()

        _loader = Loader(dature.EnvSource(), schema=_SampleDC, config=app.config)

        after = default_config.cache_info()
        assert after.misses == before.misses, "default_config() was called even though config= was passed explicitly"

    @staticmethod
    def test_env_read_only_once_across_multiple_loads(monkeypatch: pytest.MonkeyPatch) -> None:
        """default_config() is cached — env vars are read exactly once regardless of load count."""
        monkeypatch.setenv("DATURE_MASKING__MASK", "[ONCE]")
        default_config.cache_clear()

        first = default_config()
        second = default_config()
        third = default_config()

        assert first is second  # same object — read only once
        assert second is third
        assert first.masking.mask == "[ONCE]"

    @staticmethod
    def test_secret_field_names_cache_regression() -> None:
        """Regression: different secret_field_names on two Dature instances yield different secret paths.

        Before the lru_cache key fix, _compute_secret_paths read from the global config inside its
        body, so the cache key was just (dataclass_type,) and a second call with different patterns
        would silently return the first call's cached result.
        """

        @dataclass
        class MyConfig:
            token: str
            secret_key: str
            username: str

        a = Dature(masking={"secret_field_names": ("token",)})
        b = Dature(masking={"secret_field_names": ("username",)})

        paths_a = build_secret_paths(
            MyConfig,
            base_patterns=a.config.masking.secret_field_names,
        )
        paths_b = build_secret_paths(
            MyConfig,
            base_patterns=b.config.masking.secret_field_names,
        )

        assert "token" in paths_a
        assert "username" not in paths_a
        assert "username" in paths_b
        assert "token" not in paths_b

    @staticmethod
    def test_default_system_config_dirs_is_frozen() -> None:
        """The shared default LoadingConfig.system_config_dirs can't be mutated through one
        Dature() and leak into another — default_config() caches the same mapping for both.
        """
        a = Dature()
        b = Dature()

        with pytest.raises(TypeError):
            a.config.loading.system_config_dirs["linux"] = ("changed",)

        assert b.config.loading.system_config_dirs["linux"] != ("changed",)

    @staticmethod
    def test_loading_system_config_dirs_copied_from_caller_dict() -> None:
        """Dature(loading={"system_config_dirs": dirs}) must not store dirs by reference —
        mutating the caller's dict afterwards must not change the already-built config.
        """
        dirs = {"linux": ("before",)}

        app = Dature(loading={"system_config_dirs": dirs})
        dirs["linux"] = ("after",)

        assert app.config.loading.system_config_dirs["linux"] == ("before",)

    @staticmethod
    @pytest.mark.parametrize(
        ("error_display", "expected_visible_lines", "expected_max_length"),
        [
            pytest.param({"max_line_length": 40}, 3, 40, id="max_line_length_override"),
            pytest.param({"max_visible_lines": 1}, 1, 80, id="max_visible_lines_override"),
            pytest.param({}, 3, 80, id="empty_dict_resets_to_defaults"),
        ],
    )
    def test_error_display_override(
        error_display: dict[str, int],
        expected_visible_lines: int,
        expected_max_length: int,
    ) -> None:
        app = Dature(error_display=error_display)
        assert app.config.error_display.max_visible_lines == expected_visible_lines
        assert app.config.error_display.max_line_length == expected_max_length

    @staticmethod
    def test_error_display_appears_in_repr() -> None:
        app = Dature(error_display={"max_line_length": 40})
        assert "error_display=" in repr(app)

    @staticmethod
    @pytest.mark.parametrize(
        ("group", "options", "secret_value"),
        [
            pytest.param("vault", {"token": "vault-secret-token"}, "vault-secret-token", id="vault_token"),
            pytest.param("vault", {"secret_id": "vault-secret-id"}, "vault-secret-id", id="vault_secret_id"),
            pytest.param("etcd", {"password": "etcd-password"}, "etcd-password", id="etcd_password"),
            pytest.param(
                "ssm",
                {"aws_secret_access_key": "ssm-aws-secret"},
                "ssm-aws-secret",
                id="ssm_aws_secret_access_key",
            ),
            pytest.param(
                "secrets_manager",
                {"aws_secret_access_key": "sm-aws-secret"},
                "sm-aws-secret",
                id="secrets_manager_aws_secret_access_key",
            ),
            pytest.param(
                "azure_app_config",
                {"connection_string": "Endpoint=https://x.azconfig.io;Id=abc;Secret=azure-app-config-secret"},
                "azure-app-config-secret",
                id="azure_app_config_connection_string",
            ),
            pytest.param(
                "azure_key_vault",
                {"client_secret": "azure-key-vault-client-secret"},
                "azure-key-vault-client-secret",
                id="azure_key_vault_client_secret",
            ),
        ],
    )
    def test_repr_masks_secret_fields(group: str, options: dict[str, str], secret_value: str) -> None:
        app = Dature(**{group: options})
        assert secret_value not in repr(app)
        assert "<REDACTED>" in repr(app)

    @staticmethod
    def test_replace_preserves_prior_overrides() -> None:
        """Regression: replace() used to re-base on default_config(), dropping prior overrides."""
        base = Dature(masking={"mask": "[CUSTOM]"})

        derived = base.replace(loading={"debug": True})

        assert derived.config.masking.mask == "[CUSTOM]"
        assert derived.config.loading.debug is True

    @staticmethod
    def test_replace_unknown_group_raises_type_error() -> None:
        app = Dature()
        with pytest.raises(TypeError, match="vaultt"):
            app.replace(vaultt={"host": "x"})


class TestMergeGroup:
    """merge_group() must defensively copy any mapping-valued override, not just
    LoadingOptions.system_config_dirs — the fix is generic, keyed on the option's
    runtime type, not on which config group it belongs to.
    """

    @staticmethod
    def test_mapping_valued_option_is_copied_from_caller_dict() -> None:
        @dataclass(frozen=True)
        class GroupWithMapping:
            labels: dict[str, str] = field(default_factory=dict)
            tags: tuple[str, ...] = ()

        caller_dict = {"env": "prod"}
        merged = merge_group(GroupWithMapping(), {"labels": caller_dict}, GroupWithMapping)
        caller_dict["env"] = "changed"

        assert merged.labels == {"env": "prod"}

    @staticmethod
    def test_mapping_valued_option_copy_is_independent_of_result() -> None:
        @dataclass(frozen=True)
        class GroupWithMapping:
            labels: dict[str, str] = field(default_factory=dict)

        caller_dict = {"env": "prod"}
        merged = merge_group(GroupWithMapping(), {"labels": caller_dict}, GroupWithMapping)

        assert merged.labels is not caller_dict

    @staticmethod
    def test_non_mapping_option_is_passed_through_unchanged() -> None:
        @dataclass(frozen=True)
        class GroupWithTuple:
            tags: tuple[str, ...] = ()

        merged = merge_group(GroupWithTuple(), {"tags": ("a", "b")}, GroupWithTuple)

        assert merged.tags == ("a", "b")

    @staticmethod
    def test_system_config_dirs_uses_the_same_generic_path() -> None:
        """LoadingConfig.system_config_dirs is just one instance of the generic mapping-copy rule."""
        caller_dirs = {"linux": ("before",)}
        merged = merge_group(LoadingConfig(), {"system_config_dirs": caller_dirs}, LoadingConfig)
        caller_dirs["linux"] = ("after",)

        assert merged.system_config_dirs["linux"] == ("before",)


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
        default_config.cache_clear()
        with pytest.raises(DatureConfigError):
            _ = getattr(default_config(), attr)

    @staticmethod
    def test_invalid_env_raises_config_error_not_recursion_error(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATURE_MASKING__VISIBLE_PREFIX", "-1")
        default_config.cache_clear()

        with pytest.raises(DatureConfigError):
            default_config()

    @staticmethod
    def test_invalid_env_repeated_call_raises_again(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATURE_MASKING__VISIBLE_PREFIX", "-1")
        default_config.cache_clear()

        with pytest.raises(DatureConfigError):
            default_config()

        with pytest.raises(DatureConfigError):
            default_config()


@pytest.mark.usefixtures("_reset_config")
class TestResolveErrorDisplay:
    @staticmethod
    def test_returns_bootstrap_defaults_when_cache_empty() -> None:
        default_config.cache_clear()

        result = resolve_error_display()

        assert result == ErrorDisplayConfig()

    @staticmethod
    def test_returns_env_value_when_cache_populated(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATURE_ERROR_DISPLAY__MAX_LINE_LENGTH", "120")
        default_config.cache_clear()
        default_config()

        result = resolve_error_display()

        assert result.max_line_length == 120

    @staticmethod
    def test_configure_override_takes_precedence_over_cache(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATURE_ERROR_DISPLAY__MAX_LINE_LENGTH", "120")
        default_config.cache_clear()
        default_config()

        configure(error_display={"max_visible_lines": 99})
        result = resolve_error_display()

        assert result.max_visible_lines == 99
