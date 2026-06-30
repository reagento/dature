Field validators (`Annotated` predicates and `source.validators`) now fire per-source, only for fields that the source actually provided, on the coerced value. Fields that a source did not provide are not validated by that source's pass. Fields that come solely from defaults are validated once at the end on the final object.

Root validators have been promoted to a schema-level concern: pass them via `root_validators=` on `load()` / `Loader` / `configure()` — see the `schema_root_validators` and `source_root_validators` changelog entries.

Internal: validating retort is no longer built when a source has no validators (`Annotated` predicates or `source.validators` absent); single-source and multi-source loading each run one field-validation pass per source followed by a single root-retort pass at the end.
