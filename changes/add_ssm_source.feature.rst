Added :class:`AwsSsmSource` — loads configuration from AWS Systems Manager Parameter Store's
hierarchical KV tree. Install via ``pip install dature[aws]``; connection settings can be set
globally with ``configure(ssm={...})`` or ``DATURE_SSM__*`` environment variables.
Supports recursive prefix reads with automatic ``/``-based nesting, single-key JSON
documents as config roots, ``SecureString`` decryption, and ``StringList`` splitting.
With ``decode="utf-8"`` (the default), JSON-literal collection values (``[1,2,3]``,
``{"k":"v"}``) are parsed automatically, giving full type-coercion coverage matching the
other flat-key sources (ENV, Docker Secrets, ConsulSource, EtcdSource).
