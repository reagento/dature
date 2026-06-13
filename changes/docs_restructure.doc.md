Restructured the documentation:

- Added `basic/field-paths.md` — single reference page for `F` field path syntax (three forms, usage table, `F` vs `ref` distinction).
- Added section index pages (`basic/index.md`, `advanced/index.md`) with reading-order tables.
- Moved `cli_source` and `remote_source` from Basic to Advanced; split each into a concrete-source page and a custom-base-class page (`advanced/cli/argparse.md`, `advanced/cli/custom.md`, `advanced/remote/vault.md`, `advanced/remote/custom.md`). Added CLI / Remote subgroups to the Advanced nav.
- Merged `source-strategy.md` into `field-strategies.md` and renamed it `merge-strategies.md` (covers both per-field and per-source strategies in one place).
- Removed the stale `validators.md`; moved the V-DSL predicate table into `basic/validation.md`.
- Reorganised Advanced nav into four subgroups: Merging & Strategies, Sources, Values, Observability.
