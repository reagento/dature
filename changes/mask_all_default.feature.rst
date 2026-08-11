Added a masking ``masking_mode`` (``"all"`` / ``"secrets_only"`` / ``"none"``) to ``MaskingConfig``, controlling
how aggressively values are redacted in logs, error messages, and ``LoadReport``. The new default
is ``masking_mode="all"``: every string value is masked, regardless of field name or type. Set
``configure(masking={"masking_mode": "secrets_only"})`` to restore the previous behavior of masking only fields
matched by ``secret_field_names`` or ``SecretStr``/``PaymentCardNumber`` types (plus the random-string
heuristic). ``masking_mode="none"`` still disables masking entirely.

Also extended the default ``secret_field_names`` patterns to catch kebab-case field names
(``secret-key``, ``api-token``, ...) and added bare ``key``, ``uri``, and ``url`` as default patterns.

The result of a completed load (the final merged data for multi-source loads, or the loaded data
for single-source loads) is now logged at ``INFO`` instead of ``DEBUG``, so it is visible without
enabling debug logging. Per-source raw data, merge steps, and field origins remain at ``DEBUG``.
