from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Literal, cast

from adaptix.provider import Provider

from dature._deps import require_dep
from dature.sources.base import RemoteSource, string_value_loaders
from dature.type_aliases import JSONValue
from dature.validators.root import RootPredicate
from dature.validators.v import V


@dataclass(kw_only=True, repr=False)
class AwsSsmSource(RemoteSource):
    path: str
    """SSM parameter name (``recursive=False``) or path prefix (``recursive=True``)."""

    region_name: Annotated[
        str,
        (V.len() >= 1).with_error_message(
            "region_name is required (set on instance or via configure(ssm={...}) / DATURE_SSM__REGION_NAME)"
        ),
    ] = ""
    profile_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    endpoint_url: str | None = None
    """Override the SSM endpoint, e.g. to point at a LocalStack container in tests."""
    recursive: bool = True
    decrypt: bool = True
    """Whether to decrypt ``SecureString`` parameters (passed as ``WithDecryption``)."""
    decode: Literal["utf-8", "json"] = "utf-8"
    separator: str | None = "/"

    format_name: str = "ssm"
    location_label: str = "SSM"
    config_group: str | None = "ssm"

    root_validators: ClassVar[tuple[RootPredicate, ...]] = (
        V.root(
            lambda s: (s.aws_access_key_id is None) == (s.aws_secret_access_key is None),
            error_message="aws_access_key_id and aws_secret_access_key must be set together",
        ),
    )

    def remote_address(self) -> str:
        host = self.endpoint_url or self.region_name
        return f"ssm://{host}{self.path}"

    def format_loaders(self) -> "list[Provider]":
        if self.decode == "utf-8":
            return string_value_loaders()
        return super().format_loaders()

    def _build_nested(self, params: "list[dict[str, Any]]") -> JSONValue:
        """Turn a recursive ``get_parameters_by_path`` listing into a nested dict.

        The prefix (``self.path``) is stripped from every parameter name first. A name
        that matches the prefix exactly has no remainder and is dropped — it has no leaf
        name to store a value under.
        """
        root: dict[str, JSONValue] = {}
        for param in params:
            name = cast("str", param["Name"])
            remainder = name.removeprefix(self.path)
            if self.separator:
                remainder = remainder.lstrip(self.separator)
            if not remainder:
                continue
            parts = remainder.split(self.separator) if self.separator else [remainder]
            node = root
            for part in parts[:-1]:
                node = cast("dict[str, JSONValue]", node.setdefault(part, {}))
            node[parts[-1]] = self._decode_value(param)
        return root

    def _build_single(self, param: "dict[str, Any]") -> JSONValue:
        value = self._decode_value(param)
        if self.decode == "json":
            # The single parameter holds the entire config document — it *is* the root,
            # not a leaf.
            return value
        name = cast("str", param["Name"])
        last_segment = name.rsplit(self.separator, 1)[-1] if self.separator else name
        return {last_segment: value}

    def _decode_value(self, param: "dict[str, Any]") -> JSONValue:
        raw = cast("str", param["Value"])
        if param.get("Type") == "StringList":
            return cast("JSONValue", raw.split(","))
        if self.decode == "json":
            import json  # noqa: PLC0415

            return cast("JSONValue", json.loads(raw))
        return raw

    def _fetch(self) -> JSONValue:
        require_dep("boto3", "aws")
        import boto3  # noqa: PLC0415
        from botocore.exceptions import ClientError  # noqa: PLC0415

        session = boto3.Session(
            profile_name=self.profile_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
        )
        client = session.client("ssm", region_name=self.region_name, endpoint_url=self.endpoint_url)

        auth_failure_codes = {"AccessDeniedException", "UnrecognizedClientException", "InvalidSignatureException"}

        try:
            if self.recursive:
                paginator = client.get_paginator("get_parameters_by_path")
                params: list[dict[str, Any]] = []
                for page in paginator.paginate(Path=self.path, Recursive=True, WithDecryption=self.decrypt):
                    params.extend(cast("list[dict[str, Any]]", page["Parameters"]))
                found = bool(params)
                result = self._build_nested(params) if found else {}
            else:
                resp = client.get_parameter(Name=self.path, WithDecryption=self.decrypt)
                found = True
                result = self._build_single(cast("dict[str, Any]", resp["Parameter"]))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "ParameterNotFound":
                msg = f"SSM parameter not found: {self.remote_address()}"
                raise KeyError(msg) from None
            if code in auth_failure_codes:
                msg = f"AWS auth failed for {self.remote_address()}"
                raise PermissionError(msg) from None
            raise

        if not found:
            msg = f"SSM parameter not found: {self.remote_address()}"
            raise KeyError(msg) from None

        if self.decode == "utf-8":
            return self._parse_string_values(result)
        return result
