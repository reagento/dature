`loading/merge.py` repeated the same "attach load report → enrich skipped-field errors → raise"
sequence by hand at five raise sites across `_run_field_passes`, `_raise_enriched_root_error`, and
`_finalize_load`. Moved it into `_FinalizeCtx.raise_with()`, the state object each of those
functions already threads through, so the sequence lives in one place. No observable behavior
change.
