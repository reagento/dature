`LoadReport.field_origins` now lists every source that contributed to a field merged via `field_merges`. Custom strategies can narrow the list by returning `FieldMergeResult(value, contributors)`.
