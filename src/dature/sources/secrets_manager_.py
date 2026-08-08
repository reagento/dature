import json
from dataclasses import dataclass
from typing import Annotated, ClassVar, cast

from dature._deps import require_dep
from dature.sources.base import RemoteSource
from dature.type_aliases import JSONValue
from dature.validators.root import RootPredicate
from dature.validators.v import V


@dataclass(kw_only=True, repr=False)
class AwsSecretsManagerSource(RemoteSource):
    name: str
    """Secret name or ARN."""

    region_name: Annotated[
        str,
        (V.len() >= 1).with_error_message(
            "region_name is required (set on instance or via configure(secrets_manager={...}) / "
            "DATURE_SECRETS_MANAGER__REGION_NAME)"
        ),
    ] = ""
    profile_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    endpoint_url: str | None = None
    """Override the Secrets Manager endpoint, e.g. to point at a LocalStack container in tests."""
    version_id: str | None = None
    version_stage: str | None = None

    format_name: str = "secrets-manager"
    location_label: str = "SECRETS_MANAGER"
    config_group: str | None = "secrets_manager"

    root_validators: ClassVar[tuple[RootPredicate, ...]] = (
        V.root(
            lambda s: (s.aws_access_key_id is None) == (s.aws_secret_access_key is None),
            error_message="aws_access_key_id and aws_secret_access_key must be set together",
        ),
    )

    def remote_address(self) -> str:
        host = self.endpoint_url or self.region_name
        return f"secretsmanager://{host}/{self.name}"

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
        client = session.client("secretsmanager", region_name=self.region_name, endpoint_url=self.endpoint_url)

        kwargs = {"SecretId": self.name}
        if self.version_id is not None:
            kwargs["VersionId"] = self.version_id
        if self.version_stage is not None:
            kwargs["VersionStage"] = self.version_stage

        try:
            resp = client.get_secret_value(**kwargs)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "ResourceNotFoundException":
                msg = f"Secrets Manager secret not found: {self.remote_address()}"
                raise KeyError(msg) from None
            if code in {"AccessDeniedException", "UnrecognizedClientException"}:
                msg = f"AWS auth failed for {self.remote_address()}"
                raise PermissionError(msg) from None
            raise

        if "SecretString" in resp:
            payload = json.loads(resp["SecretString"])
        else:
            payload = json.loads(resp["SecretBinary"].decode("utf-8"))

        if not isinstance(payload, dict):
            msg = f"Secrets Manager secret {self.remote_address()} is not a JSON object"
            raise TypeError(msg)

        return cast("JSONValue", payload)
