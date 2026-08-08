# AwsSecretsManagerSource

`AwsSecretsManagerSource` loads configuration from [AWS Secrets
Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html) — a single
named secret holding a JSON document. It is a concrete implementation of the abstract
[`RemoteSource`](custom.md) base class and ships with the `dature[aws]` optional extra.

## Quickstart

Install the extra (pulls [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)):

```bash
pip install dature[aws]
```

```python
--8<-- "docs/examples/advanced/remote/secrets_manager/quickstart.py"
```

The secret's payload **is** the config document: no path nesting or key splitting, just a
JSON object whose top-level keys map directly to your dataclass fields.

## AwsSecretsManagerSource fields

- `name` — secret name or ARN (required).
- `region_name` — AWS region; default `""` (falls through to `SecretsManagerConfig.region_name`,
  then `"us-east-1"`).
- `profile_name` — named AWS CLI profile; default `None`.
- `aws_access_key_id` / `aws_secret_access_key` — explicit credentials; both `None` by default.
  Must be set together — setting only one raises `ValueError`. Without them, boto3's own
  credential chain applies (env vars, instance profile, SSO, etc.).
- `aws_session_token` — session token for temporary credentials; default `None`.
- `endpoint_url` — override the Secrets Manager endpoint, e.g. to point at a LocalStack
  container in tests; default `None`.
- `version_id` — specific secret version id; default `None` (latest).
- `version_stage` — specific version stage, e.g. `"AWSCURRENT"`; default `None`.

## Supported types

Like [`VaultSource`](vault.md), the secret's JSON payload is read natively — no string-based
type coercion. A secret whose value is not a JSON object (e.g. a bare string or number) raises
`TypeError`, since it cannot be the root of a config document. See
[Supported Types](../../supported_types.md) for the full matrix.

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via
`dature.configure(secrets_manager={...})` (or the matching `DATURE_SECRETS_MANAGER__*` env
vars):

```python
--8<-- "docs/examples/advanced/remote/secrets_manager/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_SECRETS_MANAGER__*` env.
`None` or `""` on the instance means "fall through to the next layer". See
[Configure](../../basic/configure.md) for the full picture.

!!! note "Credentials fall back to boto3's own chain"
    Leaving `aws_access_key_id`/`aws_secret_access_key`/`profile_name` unset does not mean
    "no auth" — boto3's `Session` still resolves credentials from environment variables, an
    EC2/ECS instance profile, or an SSO/CLI profile, exactly as it would for any other AWS SDK
    call.
