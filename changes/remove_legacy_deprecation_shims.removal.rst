Removed previously deprecated compatibility shims:

- ``skip_invalid_fields`` (``load()``/``Loader``/``--skip-invalid-fields``) — use
  ``skip_field_if_invalid`` instead.
- Passing a ``bool`` to ``skip_field_if_invalid`` — pass ``F.ANY`` (or a field-path filter) instead.
- ``Source.check_invariants()`` — use ``root_validators`` instead.
- ``Source.additional_loaders()`` — use ``format_loaders()`` instead.
- ``VaultSource.url`` / ``VaultConfig.url`` — use ``host``/``port``/``scheme`` instead.
