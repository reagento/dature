"""Integration tests for AwsSsmSource — require a live LocalStack container.

The ``integration`` marker is applied automatically by ``tests/integration/conftest.py``;
CI common jobs pass ``--ignore=tests/integration`` to skip them. To run these tests:
``uv sync --all-extras --group integration-tests --dev`` then ``pytest tests/integration``.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from dature import AwsSsmSource, configure, load
from dature.errors import DatureConfigError, SourceLocation
from dature.loading.merge_runtime import apply_source_config_group
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal

KV_PREFIX: Final = "/myapp"
ALL_TYPES_PREFIX: Final = "/all_types"
EXPECTED_SECRET: Final = {"db_password": "s3cret", "port": "5432", "name": "myapp"}


@dataclass
class _Config:
    db_password: str
    port: int
    name: str


EXPECTED_DATACLASS: Final = _Config(db_password="s3cret", port=5432, name="myapp")


@pytest.fixture
def _kv_tree(ssm_client):
    for key, value in EXPECTED_SECRET.items():
        ssm_client.put_parameter(Name=f"{KV_PREFIX}/{key}", Value=value, Type="String", Overwrite=True)


@pytest.fixture
def _kv_json_doc(ssm_client):
    ssm_client.put_parameter(Name=KV_PREFIX, Value=json.dumps(EXPECTED_SECRET), Type="String", Overwrite=True)


@pytest.fixture
def _kv_all_types(ssm_client, all_types_ssm_file: Path):
    # SSM parameters cannot store empty strings in a recursive key/value tree.
    # Store this comprehensive fixture as one JSON document so edge cases such
    # as ``empty_string=""`` are still exercised against the real SSM API.
    ssm_client.put_parameter(
        Name=ALL_TYPES_PREFIX,
        Value=all_types_ssm_file.read_text(),
        Type="String",
        Overwrite=True,
    )


def _make_source(ssm_endpoint_url, ssm_region_name, localstack_iam_credentials, **kwargs) -> AwsSsmSource:
    kwargs.setdefault("path", KV_PREFIX)
    return AwsSsmSource(
        endpoint_url=ssm_endpoint_url,
        region_name=ssm_region_name,
        aws_access_key_id=localstack_iam_credentials["aws_access_key_id"],
        aws_secret_access_key=localstack_iam_credentials["aws_secret_access_key"],
        **kwargs,
    )


@pytest.mark.usefixtures("_reset_config")
class TestAwsSsmSourceRecursive:
    @pytest.mark.usefixtures("_kv_tree")
    def test_load_basic(self, ssm_endpoint_url, ssm_region_name, localstack_iam_credentials):
        result = load(_make_source(ssm_endpoint_url, ssm_region_name, localstack_iam_credentials), schema=_Config)

        assert result == EXPECTED_DATACLASS

    def test_missing_prefix_raises(self, ssm_endpoint_url, ssm_region_name, localstack_iam_credentials):
        with pytest.raises(DatureConfigError) as exc_info:
            load(
                _make_source(
                    ssm_endpoint_url,
                    ssm_region_name,
                    localstack_iam_credentials,
                    path="/does/not/exist",
                ),
                schema=_Config,
            )

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"SSM parameter not found: ssm://{ssm_endpoint_url}/does/not/exist"

    @pytest.mark.usefixtures("_kv_tree")
    def test_resolve_location_renders_real_value(self, ssm_endpoint_url, ssm_region_name, localstack_iam_credentials):
        source = apply_source_config_group(
            _make_source(ssm_endpoint_url, ssm_region_name, localstack_iam_credentials, expand_env_vars="default")
        )

        result = source.load_raw()
        locations = source.resolve_location(
            field_path=["db_password"], nested_conflict=None, loaded_data=result.loaded_data
        )

        assert locations == [
            SourceLocation(
                location_label="SSM",
                file_path=None,
                line_range=None,
                line_content=[
                    f"ssm://{ssm_endpoint_url}{KV_PREFIX}: db_password = s3cret",
                ],
                env_var_name=None,
                line_carets=None,
            ),
        ]


@pytest.mark.usefixtures("_reset_config")
class TestAwsSsmSourceAllTypes:
    @pytest.mark.usefixtures("_kv_all_types")
    def test_comprehensive_type_conversion(self, ssm_endpoint_url, ssm_region_name, localstack_iam_credentials):
        result = load(
            _make_source(
                ssm_endpoint_url,
                ssm_region_name,
                localstack_iam_credentials,
                path=ALL_TYPES_PREFIX,
                recursive=False,
                decode="json",
            ),
            schema=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)


@pytest.mark.usefixtures("_reset_config", "_kv_json_doc")
class TestAwsSsmSourceSingleKeyJson:
    def test_load_json_document_as_root(self, ssm_endpoint_url, ssm_region_name, localstack_iam_credentials):
        result = load(
            _make_source(
                ssm_endpoint_url,
                ssm_region_name,
                localstack_iam_credentials,
                recursive=False,
                decode="json",
            ),
            schema=_Config,
        )

        assert result == EXPECTED_DATACLASS


@pytest.mark.usefixtures("_reset_config")
class TestAwsSsmSourceAuth:
    @pytest.mark.usefixtures("_kv_tree")
    def test_iam_user_credentials_load_config(self, ssm_endpoint_url, ssm_region_name, localstack_iam_credentials):
        source = _make_source(ssm_endpoint_url, ssm_region_name, localstack_iam_credentials)

        result = load(source, schema=_Config)

        assert result == EXPECTED_DATACLASS

    @pytest.mark.usefixtures("_kv_tree")
    def test_wrong_credentials_raise_config_error(
        self,
        ssm_endpoint_url,
        ssm_region_name,
        localstack_wrong_account_credentials,
    ):
        source = _make_source(ssm_endpoint_url, ssm_region_name, localstack_wrong_account_credentials)

        with pytest.raises(DatureConfigError) as exc_info:
            load(source, schema=_Config)

        inner = exc_info.value.exceptions[0]
        assert isinstance(inner, KeyError)
        assert inner.args[0] == f"SSM parameter not found: ssm://{ssm_endpoint_url}{KV_PREFIX}"


@pytest.mark.usefixtures("_reset_config", "_kv_tree")
class TestAwsSsmSourceGlobalConfigEndToEnd:
    @pytest.mark.parametrize(
        "via",
        [
            pytest.param("configure", id="settings_from_configure"),
            pytest.param("env", id="settings_from_env"),
        ],
    )
    def test_load_with_settings(self, via, ssm_endpoint_url, ssm_region_name, localstack_iam_credentials, monkeypatch):
        settings = {
            "region_name": ssm_region_name,
            "endpoint_url": ssm_endpoint_url,
            "aws_access_key_id": localstack_iam_credentials["aws_access_key_id"],
            "aws_secret_access_key": localstack_iam_credentials["aws_secret_access_key"],
        }
        if via == "configure":
            configure(ssm=settings)
        else:
            monkeypatch.setenv("DATURE_SSM__REGION_NAME", ssm_region_name)
            monkeypatch.setenv("DATURE_SSM__ENDPOINT_URL", ssm_endpoint_url)
            monkeypatch.setenv("DATURE_SSM__AWS_ACCESS_KEY_ID", localstack_iam_credentials["aws_access_key_id"])
            monkeypatch.setenv("DATURE_SSM__AWS_SECRET_ACCESS_KEY", localstack_iam_credentials["aws_secret_access_key"])

        result = load(AwsSsmSource(path=KV_PREFIX), schema=_Config)

        assert result == EXPECTED_DATACLASS
