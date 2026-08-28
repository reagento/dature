# AwsSsmSource

`AwsSsmSource` loads configuration from [AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)'s hierarchical KV tree. It is a concrete implementation of the abstract [`RemoteSource`](custom.md) base class and ships with the `dature[aws]` optional extra.

## Quickstart

Install the extra (pulls [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)):

```bash
pip install dature[aws]
```

```python
--8<-- "docs/examples/advanced/remote/ssm/quickstart.py"
```

By default `AwsSsmSource` reads recursively (`recursive=True`) and splits parameter names on `/`, nesting them into a dict hierarchy. With the parameters `/myapp/db_password = s3cret`, `/myapp/port = 5432`, `/myapp/name = myapp` and `path="/myapp"` the loaded dict is `{"db_password": "s3cret", "port": "5432", "name": "myapp"}`, which maps directly to a flat dataclass.

## AwsSsmSource fields

- `path` — parameter name (`recursive=False`) or path prefix (`recursive=True`) (required).
- `region_name` — AWS region; default `""` (falls through to `SsmConfig.region_name`, then `"us-east-1"`).
- `profile_name` — named AWS CLI profile; default `None`.
- `aws_access_key_id` / `aws_secret_access_key` — explicit credentials; both `None` by default. Must be set together — setting only one raises `ValueError`. Without them, boto3's own credential chain applies (env vars, instance profile, SSO, etc.).
- `aws_session_token` — session token for temporary credentials; default `None`.
- `endpoint_url` — override the SSM endpoint, e.g. to point at a LocalStack container in tests; default `None`.
- `recursive` — read the path prefix recursively; default `True`.
- `decrypt` — decrypt `SecureString` parameters (passed as `WithDecryption`); default `True`.
- `decode` — how to decode each value: `"utf-8"` (default) or `"json"`.
- `separator` — path segment separator for nesting; default `"/"`. Set to `None` to disable nesting. Parameters of type `StringList` are always split into a list on `,` regardless of `decode`.

## Supported types

With `decode="utf-8"` (the default) every value is a string and collections are JSON literals — the same dialect as ENV, with `/` nesting instead of `__`. `decode="json"` behaves like [`VaultSource`](vault.md) (native JSON), reading a single parameter whose value is an entire JSON document. See [Supported Types](../../supported_types.md) for the full matrix.

## Global configuration via configure()

Connection settings rarely change per-call, so they can be set once via `dature.configure(ssm={...})` (or the matching `DATURE_SSM__*` env vars):

```python
--8<-- "docs/examples/advanced/remote/ssm/configure.py"
```

Precedence (highest first): instance fields → `configure()` → `DATURE_SSM__*` env. `None` or `""` on the instance means "fall through to the next layer". See [Configure](../../basic/configure.md) for the full picture.

!!! note "Pagination"
    `get_parameters_by_path` returns at most 10 parameters per page. `AwsSsmSource` always paginates through the full result set, so large parameter trees are read completely.

!!! note "Credentials fall back to boto3's own chain"
    Leaving `aws_access_key_id`/`aws_secret_access_key`/`profile_name` unset does not mean "no auth" — boto3's `Session` still resolves credentials from environment variables, an EC2/ECS instance profile, or an SSO/CLI profile, exactly as it would for any other AWS SDK call.
