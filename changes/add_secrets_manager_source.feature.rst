Added :class:`AwsSecretsManagerSource` — loads configuration from a single named AWS
Secrets Manager secret holding a JSON document. Install via ``pip install dature[aws]``;
connection settings can be set globally with ``configure(secrets_manager={...})`` or
``DATURE_SECRETS_MANAGER__*`` environment variables. Like :class:`VaultSource`, the
secret's JSON payload is read natively as the config root — no path nesting or key
splitting. Supports both ``SecretString`` and ``SecretBinary`` payloads, plus
``version_id``/``version_stage`` selection.
