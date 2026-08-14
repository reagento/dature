"""Integration tests for AwsSecretsManagerSource — require a live LocalStack container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from dature import AwsSecretsManagerSource, configure, load
from dature.errors import DatureConfigError, SourceLocation
from dature.loading.merge_runtime import apply_source_config_group
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal

SECRET_NAME: Final = "myapp/config"
EXPECTED_SECRET: Final = {"db_password": "s3cret", "port": 5432, "name": "myapp"}


@dataclass
class _Config:
    db_password: str
    port: int
    name: str


EXPECTED_DATACLASS: Final = _Config(db_password="s3cret", port=5432, name="myapp")


@pytest.fixture
def _secret(secrets_manager_put_secret):
    secrets_manager_put_secret(name=SECRET_NAME, secret_string=json.dumps(EXPECTED_SECRET))


@pytest.fixture
def _all_types_secret(secrets_manager_put_secret, all_types_secrets_manager_file: Path):
    secrets_manager_put_secret(name=SECRET_NAME, secret_string=all_types_secrets_manager_file.read_text())


def _make_source(
    secrets_manager_endpoint_url,
    secrets_manager_region_name,
    localstack_iam_credentials,
    **kwargs,
) -> AwsSecretsManagerSource:
    kwargs.setdefault("name", SECRET_NAME)
    return AwsSecretsManagerSource(
        endpoint_url=secrets_manager_endpoint_url,
        region_name=secrets_manager_region_name,
        aws_access_key_id=localstack_iam_credentials["aws_access_key_id"],
        aws_secret_access_key=localstack_iam_credentials["aws_secret_access_key"],
        **kwargs,
    )


@pytest.mark.usefixtures("_reset_config", "_secret")
class TestAwsSecretsManagerSourceLoad:
    def test_load_basic(self, secrets_manager_endpoint_url, secrets_manager_region_name, localstack_iam_credentials):
        result = load(
            _make_source(secrets_manager_endpoint_url, secrets_manager_region_name, localstack_iam_credentials),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS

    def test_resolve_location_renders_real_value(
        self,
        secrets_manager_endpoint_url,
        secrets_manager_region_name,
        localstack_iam_credentials,
    ):
        source = apply_source_config_group(
            _make_source(
                secrets_manager_endpoint_url,
                secrets_manager_region_name,
                localstack_iam_credentials,
                expand_env_vars="default",
            ),
        )

        result = source.load_raw()
        locations = source.resolve_location(
            field_path=["db_password"], nested_conflict=None, loaded_data=result.loaded_data
        )

        assert locations == [
            SourceLocation(
                location_label="SECRETS_MANAGER",
                file_path=None,
                line_range=None,
                line_content=[
                    f"secretsmanager://{secrets_manager_endpoint_url}/{SECRET_NAME}: db_password = s3cret",
                ],
                env_var_name=None,
                line_carets=None,
            ),
        ]


@pytest.mark.usefixtures("_reset_config")
class TestAwsSecretsManagerSourceMissing:
    def test_missing_secret_raises(
        self,
        secrets_manager_endpoint_url,
        secrets_manager_region_name,
        localstack_iam_credentials,
    ):
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                _make_source(
                    secrets_manager_endpoint_url,
                    secrets_manager_region_name,
                    localstack_iam_credentials,
                    name="does-not-exist",
                ),
                schema=_Config,
            )

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == (
            f"Secrets Manager secret not found: secretsmanager://{secrets_manager_endpoint_url}/does-not-exist"
        )


@pytest.mark.usefixtures("_reset_config")
class TestAwsSecretsManagerSourceAllTypes:
    @pytest.mark.usefixtures("_all_types_secret")
    def test_comprehensive_type_conversion(
        self,
        secrets_manager_endpoint_url,
        secrets_manager_region_name,
        localstack_iam_credentials,
    ):
        result = load(
            _make_source(secrets_manager_endpoint_url, secrets_manager_region_name, localstack_iam_credentials),
            schema=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config")
class TestAwsSecretsManagerSourceAuth:
    def test_iam_user_credentials_load_config(
        self,
        secrets_manager_endpoint_url,
        secrets_manager_region_name,
        secrets_manager_put_secret,
        localstack_iam_credentials,
    ):
        secrets_manager_put_secret(name=SECRET_NAME, secret_string=json.dumps(EXPECTED_SECRET))
        source = _make_source(secrets_manager_endpoint_url, secrets_manager_region_name, localstack_iam_credentials)

        result = load(source, schema=_Config)

        assert result == EXPECTED_DATACLASS

    def test_wrong_credentials_raise_config_error(
        self,
        secrets_manager_endpoint_url,
        secrets_manager_region_name,
        secrets_manager_put_secret,
        localstack_wrong_account_credentials,
    ):
        secrets_manager_put_secret(name=SECRET_NAME, secret_string=json.dumps(EXPECTED_SECRET))
        source = _make_source(
            secrets_manager_endpoint_url,
            secrets_manager_region_name,
            localstack_wrong_account_credentials,
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(source, schema=_Config)

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == (
            f"Secrets Manager secret not found: secretsmanager://{secrets_manager_endpoint_url}/{SECRET_NAME}"
        )


@pytest.mark.usefixtures("_reset_config", "_secret")
class TestAwsSecretsManagerSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="settings_from_configure"),
            pytest.param("env", id="settings_from_env"),
        ],
    )
    def test_load_with_settings(
        self,
        via,
        secrets_manager_endpoint_url,
        secrets_manager_region_name,
        localstack_iam_credentials,
        monkeypatch,
    ):
        settings = {
            "region_name": secrets_manager_region_name,
            "endpoint_url": secrets_manager_endpoint_url,
            "aws_access_key_id": localstack_iam_credentials["aws_access_key_id"],
            "aws_secret_access_key": localstack_iam_credentials["aws_secret_access_key"],
        }
        if via == "configure":
            configure(secrets_manager=settings)
        else:
            monkeypatch.setenv("DATURE_SECRETS_MANAGER__REGION_NAME", secrets_manager_region_name)
            monkeypatch.setenv("DATURE_SECRETS_MANAGER__ENDPOINT_URL", secrets_manager_endpoint_url)
            monkeypatch.setenv(
                "DATURE_SECRETS_MANAGER__AWS_ACCESS_KEY_ID",
                localstack_iam_credentials["aws_access_key_id"],
            )
            monkeypatch.setenv(
                "DATURE_SECRETS_MANAGER__AWS_SECRET_ACCESS_KEY",
                localstack_iam_credentials["aws_secret_access_key"],
            )

        result = load(AwsSecretsManagerSource(name=SECRET_NAME), schema=_Config)

        assert result == EXPECTED_DATACLASS
