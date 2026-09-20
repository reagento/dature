A cross-source reference (`${@tag.key}`) substituted into another source's init field
(`file=`, `dir_=`, a remote source's host/path/…) surfaced in cleartext in the debug report
(`SourceEntry.file_path` / `FieldOrigin.source_file`), error messages, and `repr()`, even when
`key` looked like a secret (e.g. `${@vault.db_password}`) — masking only ever covered
structured document data, never a source's own init-field values. `masking_mode="none"` was
also ignored for this case, redacting even when masking was explicitly disabled.

Every source now records `(raw, masked)` pairs for substituted values whose ref matched the
secret-name heuristic, masking each with the effective `MaskingConfig` (`mask`,
`visible_prefix`, `visible_suffix`) — the same rule already used for schema-field masking, and
respecting `masking_mode`. Display surfaces (file paths in reports, error locations, `repr()`,
remote addresses) redact only the secret substring, e.g. `/cfg/<REDACTED>.json` instead of
losing the whole path — the real value is still used to do the source's job (e.g. open the
file), only its display is affected.
