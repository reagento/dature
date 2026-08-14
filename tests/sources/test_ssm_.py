"""Unit tests for ssm_ module (AwsSsmSource).

Container-based integration tests live in ``tests/integration/sources/ssm/``.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError

from dature import AwsSsmSource, configure, load
from dature.errors import DatureConfigError
from dature.loading.merge_runtime import apply_source_config_group
from dature.loading.source_validation import validate_source
from dature.sources.base import remote_value_loaders, string_value_loaders
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestAwsSsmSourceDisplayProperties:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("format_name", "ssm", id="format_name"),
            pytest.param("location_label", "SSM", id="location_label"),
            pytest.param("config_group", "ssm", id="config_group"),
        ],
    )
    def test_class_attribute(self, attr, expected):
        assert getattr(AwsSsmSource, attr) == expected

    @pytest.mark.parametrize(
        ("decode", "expected"),
        [
            pytest.param("utf-8", string_value_loaders(), id="utf8"),
            pytest.param("json", remote_value_loaders(), id="json"),
        ],
    )
    def test_format_loaders(self, decode, expected):
        src = AwsSsmSource(path="/myapp/", region_name="us-east-1", decode=decode)

        loaders = src.format_loaders()

        assert loaders == expected

    def test_format_loaders_raises_on_unknown_decode(self):
        src = AwsSsmSource(path="/myapp/", region_name="us-east-1", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src.format_loaders()

    def test_decode_value_raises_on_unknown_decode(self):
        src = AwsSsmSource(path="/myapp/", region_name="us-east-1", decode="xml")

        with pytest.raises(ValueError, match="Unknown decode mode: 'xml'"):
            src._decode_value({"Name": "/myapp/x", "Value": "v", "Type": "String"})

    @pytest.mark.parametrize(
        ("region_name", "path", "endpoint_url", "expected"),
        [
            pytest.param("us-east-1", "/myapp/config", None, "ssm://us-east-1/myapp/config", id="region"),
            pytest.param(
                "us-east-1",
                "/myapp/config",
                "http://localhost:4566",
                "ssm://http://localhost:4566/myapp/config",
                id="endpoint_url_overrides_region",
            ),
        ],
    )
    def test_remote_address(self, region_name, path, endpoint_url, expected):
        src = AwsSsmSource(path=path, region_name=region_name, endpoint_url=endpoint_url)

        address = src.remote_address()

        assert address == expected


@pytest.mark.usefixtures("_reset_config")
class TestAwsSsmSourceValidation:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            pytest.param(
                {"path": "p", "region_name": "us-east-1", "aws_access_key_id": "k"},
                "must be set together",
                id="access_key_without_secret",
            ),
            pytest.param(
                {"path": "p", "region_name": "us-east-1", "aws_secret_access_key": "s"},
                "must be set together",
                id="secret_without_access_key",
            ),
        ],
    )
    def test_validate_raises_when_invalid(self, kwargs, match):
        merged = apply_source_config_group(AwsSsmSource(**kwargs))

        with pytest.raises(ValueError, match=match):
            validate_source(merged)

    def test_no_region_raises(self):
        # SsmConfig defaults region_name to "us-east-1", so the fallback group always fills
        # it in — "region_name is required" is only reachable when validate_source() runs on
        # a bare instance that skipped the config-group merge (e.g. config_group=None).
        src = AwsSsmSource(path="p")

        with pytest.raises(ValueError, match="region_name is required"):
            validate_source(src)

    def test_validate_passes(self):
        merged = apply_source_config_group(AwsSsmSource(path="p"))

        validate_source(merged)

    def test_validate_passes_with_access_key_pair(self):
        merged = apply_source_config_group(AwsSsmSource(path="p", aws_access_key_id="k", aws_secret_access_key="s"))

        validate_source(merged)


@pytest.mark.usefixtures("_reset_config")
class TestAwsSsmSourceConfigFallback:
    def test_region_from_configure(self):
        configure(ssm={"region_name": "eu-west-1"})

        merged = apply_source_config_group(AwsSsmSource(path="p"))

        assert merged.region_name == "eu-west-1"

    def test_creds_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DATURE_SSM__REGION_NAME", "eu-west-1")
        monkeypatch.setenv("DATURE_SSM__PROFILE_NAME", "dev")

        merged = apply_source_config_group(AwsSsmSource(path="/myapp/"))

        assert merged.region_name == "eu-west-1"
        assert merged.profile_name == "dev"

    def test_instance_overrides_global(self):
        configure(ssm={"region_name": "global-region"})

        merged = apply_source_config_group(AwsSsmSource(path="p", region_name="instance-region"))

        assert merged.region_name == "instance-region"


class FakePaginator:
    def __init__(self, pages: object) -> None:
        self._pages = pages

    def paginate(self, **kwargs: object) -> object:
        self.paginate_kwargs = kwargs
        return self._pages


class FakeSsmClient:
    """Stand-in for boto3's SSM client."""

    def __init__(
        self,
        *,
        pages: object = None,
        parameter: object = None,
        error: Exception | None = None,
    ) -> None:
        self._pages = pages if pages is not None else []
        self._parameter = parameter
        self._error = error
        self.get_parameter_kwargs: dict[str, object] | None = None
        self.paginator: FakePaginator | None = None

    def get_paginator(self, name: str) -> FakePaginator:
        assert name == "get_parameters_by_path"
        if self._error is not None:
            raise self._error
        self.paginator = FakePaginator(self._pages)
        return self.paginator

    def get_parameter(self, **kwargs: object) -> dict[str, object]:
        self.get_parameter_kwargs = kwargs
        if self._error is not None:
            raise self._error
        return {"Parameter": self._parameter}


class FakeSession:
    def __init__(self, client: FakeSsmClient) -> None:
        self._client = client

    def client(self, service: str, **kwargs: object) -> FakeSsmClient:  # noqa: ARG002
        assert service == "ssm"
        return self._client


@dataclass
class _FetchConfig:
    port: int


class TestAwsSsmSourceFetch:
    def _make_source(self, monkeypatch: pytest.MonkeyPatch, client: FakeSsmClient, **kwargs: object) -> AwsSsmSource:
        monkeypatch.setattr(boto3, "Session", lambda **kw: FakeSession(client))  # noqa: ARG005
        kwargs.setdefault("path", "/myapp")
        kwargs.setdefault("expand_env_vars", "default")
        return AwsSsmSource(region_name="us-east-1", **kwargs)

    def test_recursive_nests_on_separator(self, monkeypatch):
        params = [
            {"Name": "/myapp/db/host", "Value": "localhost", "Type": "String"},
            {"Name": "/myapp/db/port", "Value": "5432", "Type": "String"},
            {"Name": "/myapp/name", "Value": "svc", "Type": "String"},
        ]
        client = FakeSsmClient(pages=[{"Parameters": params}])
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {
            "db": {"host": "localhost", "port": 5432},
            "name": "svc",
        }

    def test_recursive_paginates_across_pages(self, monkeypatch):
        pages = [
            {"Parameters": [{"Name": "/myapp/a", "Value": "1", "Type": "String"}]},
            {"Parameters": [{"Name": "/myapp/b", "Value": "2", "Type": "String"}]},
        ]
        client = FakeSsmClient(pages=pages)
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"a": "1", "b": "2"}

    def test_recursive_drops_exact_prefix_key(self, monkeypatch):
        params = [
            {"Name": "/myapp", "Value": "", "Type": "String"},
            {"Name": "/myapp/name", "Value": "svc", "Type": "String"},
        ]
        client = FakeSsmClient(pages=[{"Parameters": params}])
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"name": "svc"}

    def test_recursive_separator_none_keeps_flat_keys(self, monkeypatch):
        params = [
            {"Name": "/myapp/db/host", "Value": "localhost", "Type": "String"},
            {"Name": "/myapp/name", "Value": "svc", "Type": "String"},
        ]
        client = FakeSsmClient(pages=[{"Parameters": params}])
        src = self._make_source(monkeypatch, client, separator=None)

        result = src.load_raw()

        assert result.loaded_data == {
            "/db/host": "localhost",
            "/name": "svc",
        }

    def test_string_list_becomes_list(self, monkeypatch):
        params = [{"Name": "/myapp/tags", "Value": "a,b,c", "Type": "StringList"}]
        client = FakeSsmClient(pages=[{"Parameters": params}])
        src = self._make_source(monkeypatch, client)

        result = src.load_raw()

        assert result.loaded_data == {"tags": ["a", "b", "c"]}

    def test_decrypt_flag_passed_as_with_decryption(self, monkeypatch):
        params = [{"Name": "/myapp/a", "Value": "1", "Type": "String"}]
        client = FakeSsmClient(pages=[{"Parameters": params}])
        src = self._make_source(monkeypatch, client, decrypt=False)

        src.load_raw()

        assert client.paginator is not None
        assert client.paginator.paginate_kwargs["WithDecryption"] is False

    def test_single_key_json_becomes_root(self, monkeypatch):
        client = FakeSsmClient(parameter={"Name": "/myapp/config", "Value": '{"db": {"host": "localhost"}}'})
        src = self._make_source(monkeypatch, client, recursive=False, decode="json")

        result = src.load_raw()

        assert result.loaded_data == {"db": {"host": "localhost"}}

    def test_single_key_non_json_uses_last_segment(self, monkeypatch):
        client = FakeSsmClient(parameter={"Name": "/myapp/name", "Value": "svc"})
        src = self._make_source(monkeypatch, client, path="/myapp/name", recursive=False)

        result = src.load_raw()

        assert result.loaded_data == {"name": "svc"}

    def test_missing_prefix_raises_key_error(self, monkeypatch):
        client = FakeSsmClient(pages=[{"Parameters": []}])
        src = self._make_source(monkeypatch, client)

        with pytest.raises(KeyError, match="SSM parameter not found"):
            src.load_raw()

    def test_missing_single_key_raises_key_error(self, monkeypatch):
        error = ClientError({"Error": {"Code": "ParameterNotFound", "Message": "x"}}, "GetParameter")
        client = FakeSsmClient(error=error)
        src = self._make_source(monkeypatch, client, recursive=False)

        with pytest.raises(KeyError, match="SSM parameter not found"):
            src.load_raw()

    @pytest.mark.parametrize(
        "code",
        ["AccessDeniedException", "UnrecognizedClientException", "InvalidSignatureException"],
    )
    def test_auth_failure_raises_permission_error(self, monkeypatch, code):
        error = ClientError({"Error": {"Code": code, "Message": "x"}}, "GetParametersByPath")
        client = FakeSsmClient(error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(PermissionError, match="AWS auth failed"):
            src.load_raw()

    def test_other_client_error_propagates(self, monkeypatch):
        error = ClientError({"Error": {"Code": "ThrottlingException", "Message": "x"}}, "GetParametersByPath")
        client = FakeSsmClient(error=error)
        src = self._make_source(monkeypatch, client)

        with pytest.raises(ClientError):
            src.load_raw()

    def test_comprehensive_type_conversion(self, monkeypatch, all_types_etcd_kv_file: Path):
        """Test loading a recursive SSM parameter tree (decode='utf-8') with full type coercion."""
        kv_map = json.loads(all_types_etcd_kv_file.read_text())
        params = [
            {"Name": "/" + key.replace("all_types", "myapp", 1), "Value": value, "Type": "String"}
            for key, value in kv_map.items()
        ]
        client = FakeSsmClient(pages=[{"Parameters": params}])
        src = self._make_source(monkeypatch, client)

        result = load(src, schema=AllPythonTypesCompact)

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_missing_key_error_message_includes_path(self, monkeypatch):
        client = FakeSsmClient(pages=[{"Parameters": []}])
        self._make_source(monkeypatch, client)

        with pytest.raises(DatureConfigError) as exc_info:
            load(AwsSsmSource(region_name="us-east-1", path="/myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == "'SSM parameter not found: ssm://us-east-1/myapp'"

    def test_bad_type_error_message_includes_path_and_value(self, monkeypatch):
        params = [{"Name": "/myapp/port", "Value": "not_a_number", "Type": "String"}]
        client = FakeSsmClient(pages=[{"Parameters": params}])
        self._make_source(monkeypatch, client)

        with pytest.raises(DatureConfigError) as exc_info:
            load(AwsSsmSource(region_name="us-east-1", path="/myapp"), schema=_FetchConfig)

        assert len(exc_info.value.exceptions) == 1
        assert str(exc_info.value.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: '<REDACTED>'\n"
            "   ├── ssm://us-east-1/myapp: port = <REDACTED>\n"
            "   │                                 ^^^^^^^^^^"
        )


@pytest.mark.usefixtures("_reset_config")
def test_missing_boto3_raises_on_load(block_import, monkeypatch):
    """`import dature` works without boto3; only _fetch() requires it."""
    monkeypatch.setenv("DATURE_SSM__REGION_NAME", "us-east-1")

    @dataclass
    class Config:
        foo: str = ""

    with block_import("boto3"), pytest.raises(DatureConfigError) as exc_info:
        load(AwsSsmSource(path="/myapp"), schema=Config)

    assert isinstance(exc_info.value.exceptions[0], ImportError)
    assert str(exc_info.value.exceptions[0]) == "'boto3' is not installed. Run: pip install 'dature[aws]'"
