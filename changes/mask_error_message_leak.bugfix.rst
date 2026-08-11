Fixed error messages leaking the raw offending value even when masking was active: coercion
failures (e.g. ``int("not_a_number")``, invalid ``timedelta``/``ByteSize``/card-number formats)
bake the literal input into the exception text (``invalid literal for int() with base 10:
'secret'``), and this text was returned verbatim regardless of ``masking_mode`` — only the
displayed source line was masked, not the message itself. The raw value is now redacted from the
message too whenever the field is considered secret (``masking_mode="all"``, an explicit secret
path, or the random-string heuristic under ``"secrets_only"``).
