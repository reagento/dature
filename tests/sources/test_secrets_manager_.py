"""Unit tests for secrets_manager_ module (AwsSecretsManagerSource).

Container-based integration tests live in ``tests/integration/sources/secrets_manager/``.
"""

from dataclasses import dataclass
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError

from dature import AwsSecretsManagerSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group
from dature.loading.source_validation import validate_source
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestAwsSecretsManagerSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "secrets-manager", id="format_name"),
            pytest.param("location_label", "SECRETS_MANAGER", id="location_label"),
            pytest.param("config_group", "secrets_manager", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(AwsSecretsManagerSource, attr) == expected

    def test_remote_address(self):
        src = AwsSecretsManagerSource(name="myapp/config", region_name="us-east-1")

        assert src.remote_address() == "secretsmanager://us-east-1/myapp/config"

    def test_remote_address_endpoint_url_overrides_region(self):
        src = AwsSecretsManagerSource(
            name="myapp/config", region_name="us-east-1", endpoint_url="http://localhost:4566"
        )

        assert src.remote_address() == "secretsmanager://http://localhost:4566/myapp/config"


@pytest.mark.usefixtures("_reset_config")
class TestAwsSecretsManagerSourceValidation:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            pytest.param(
                {"name": "s", "region_name": "us-east-1", "aws_access_key_id": "k"},
                "must be set together",
                id="access_key_without_secret",
            ),
            pytest.param(
                {"name": "s", "region_name": "us-east-1", "aws_secret_access_key": "s"},
                "must be set together",
                id="secret_without_access_key",
            ),
        ],
    )
    def test_validate_raises_when_invalid(self, kwargs, match):
        merged = apply_source_config_group(AwsSecretsManagerSource(**kwargs))

        with pytest.raises(ValueError, match=match):
            validate_source(merged)

    def test_no_region_raises(self):
        # SecretsManagerConfig defaults region_name to "us-east-1", so the fallback group
        # always fills it in — "region_name is required" is only reachable when
        # validate_source() runs on a bare instance that skipped the config-group merge.
        src = AwsSecretsManagerSource(name="s")

        with pytest.raises(ValueError, match="region_name is required"):
            validate_source(src)

    def test_validate_passes(self):
        merged = apply_source_config_group(AwsSecretsManagerSource(name="s"))

        validate_source(merged)

    def test_validate_passes_with_access_key_pair(self):
        merged = apply_source_config_group(
            AwsSecretsManagerSource(name="s", aws_access_key_id="k", aws_secret_access_key="s")
        )

        validate_source(merged)


@pytest.mark.usefixtures("_reset_config")
class TestAwsSecretsManagerSourceConfigFallback:
    def test_region_from_configure(self):
        configure(secrets_manager={"region_name": "eu-west-1"})

        merged = apply_source_config_group(AwsSecretsManagerSource(name="s"))

        assert merged.region_name == "eu-west-1"

    def test_creds_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DATURE_SECRETS_MANAGER__REGION_NAME", "eu-west-1")
        monkeypatch.setenv("DATURE_SECRETS_MANAGER__PROFILE_NAME", "dev")

        merged = apply_source_config_group(AwsSecretsManagerSource(name="myapp/config"))

        assert merged.region_name == "eu-west-1"
        assert merged.profile_name == "dev"

    def test_instance_overrides_global(self):
        configure(secrets_manager={"region_name": "global-region"})

        merged = apply_source_config_group(AwsSecretsManagerSource(name="s", region_name="instance-region"))

        assert merged.region_name == "instance-region"


class FakeSecretsManagerClient:
    """Stand-in for boto3's Secrets Manager client."""

    def __init__(
        self,
        *,
        secret_string: str | None = None,
        secret_binary: bytes | None = None,
        error: Exception | None = None,
    ) -> None:
        self._secret_string = secret_string
        self._secret_binary = secret_binary
        self._error = error
        self.get_secret_value_kwargs: dict[str, object] | None = None

    def get_secret_value(self, **kwargs: object) -> dict[str, object]:
        self.get_secret_value_kwargs = kwargs
        if self._error is not None:
            raise self._error
        if self._secret_binary is not None:
            return {"SecretBinary": self._secret_binary}
        return {"SecretString": self._secret_string}


class FakeSession:
    def __init__(self, client: FakeSecretsManagerClient) -> None:
        self._client = client

    def client(self, service: str, **kwargs: object) -> FakeSecretsManagerClient:  # noqa: ARG002
        assert service == "secretsmanager"
        return self._client


@dataclass
class _FetchConfig:
    port: int


class TestAwsSecretsManagerSourceFetch:
    def _make_source(
        self, monkeypatch: pytest.MonkeyPatch, client: FakeSecretsManagerClient, **kwargs: object
    ) -> AwsSecretsManagerSource:
        monkeypatch.setattr(boto3, "Session", lambda **kw: FakeSession(client))  # noqa: ARG005
        kwargs.setdefault("name", "myapp/config")
        return AwsSecretsManagerSource(region_name="us-east-1", **kwargs)

    def test_secret_string_is_parsed(self, monkeypatch):
        client = FakeSecretsManagerClient(secret_string='{"host": "localhost", "port": 5432}')
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"host": "localhost", "port": 5432}

    def test_secret_binary_is_parsed(self, monkeypatch):
        client = FakeSecretsManagerClient(secret_binary=b'{"host": "localhost"}')
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"host": "localhost"}

    def test_version_id_and_stage_passed_through(self, monkeypatch):
        client = FakeSecretsManagerClient(secret_string="{}")
        src = self._make_source(monkeypatch, client, version_id="v1", version_stage="AWSCURRENT")

        src.load_raw()

        assert client.get_secret_value_kwargs["VersionId"] == "v1"
        assert client.get_secret_value_kwargs["VersionStage"] == "AWSCURRENT"

    def test_non_mapping_payload_raises_type_error(self, monkeypatch):
        client = FakeSecretsManagerClient(secret_string="42")
        src = self._make_source(monkeypatch, client)

        with pytest.raises(TypeError, match="is not a JSON object"):
            src.load_raw()

    def test_missing_secret_raises_key_error(self, monkeypatch):
        error = ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "x"}}, "GetSecretValue")
        client = FakeSecretsManagerClient(error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(KeyError, match="Secrets Manager secret not found"):
            src.load_raw()

    @pytest.mark.parametrize("code", ["AccessDeniedException", "UnrecognizedClientException"])
    def test_auth_failure_raises_permission_error(self, monkeypatch, code):
        error = ClientError({"Error": {"Code": code, "Message": "x"}}, "GetSecretValue")
        client = FakeSecretsManagerClient(error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(PermissionError, match="AWS auth failed"):
            src.load_raw()

    def test_other_client_error_propagates(self, monkeypatch):
        error = ClientError({"Error": {"Code": "ThrottlingException", "Message": "x"}}, "GetSecretValue")
        client = FakeSecretsManagerClient(error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(ClientError):
            src.load_raw()

    def test_comprehensive_type_conversion(self, monkeypatch, all_types_vault_file: Path):
        """Test loading Secrets Manager's native-JSON payload with full type coercion."""
        payload = all_types_vault_file.read_text()
        client = FakeSecretsManagerClient(secret_string=payload)
        src = self._make_source(monkeypatch, client)

        result = load(src, schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_missing_secret_error_message_includes_path(self, monkeypatch):
        error = ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "x"}}, "GetSecretValue")
        client = FakeSecretsManagerClient(error=error)
        self._make_source(monkeypatch, client)

        with pytest.raises(DatureConfigError) as exc_info:
            load(AwsSecretsManagerSource(region_name="us-east-1", name="myapp/config"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "'Secrets Manager secret not found: secretsmanager://us-east-1/myapp/config'"
        )

    def test_bad_type_error_message_includes_path_and_value(self, monkeypatch):
        client = FakeSecretsManagerClient(secret_string='{"port": "not_a_number"}')
        self._make_source(monkeypatch, client)

        with pytest.raises(DatureConfigError) as exc_info:
            load(AwsSecretsManagerSource(region_name="us-east-1", name="myapp/config"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: 'not_a_number'\n"
            "   ├── secretsmanager://us-east-1/myapp/config: port = not_a_number"
        )


@pytest.mark.usefixtures("_reset_config")
def test_missing_boto3_raises_on_load(block_import, monkeypatch):
    """`import dature` works without boto3; only _fetch() requires it."""
    monkeypatch.setenv("DATURE_SECRETS_MANAGER__REGION_NAME", "us-east-1")

    @dataclass
    class Config:
        foo: str = ""

    with block_import("boto3"), pytest.raises(DatureConfigError) as exc_info:
        load(AwsSecretsManagerSource(name="myapp/config"), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == "'boto3' is not installed. Run: pip install 'dature[aws]'"
