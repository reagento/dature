Made merge strategies pluggable via a `Protocol`-based class API.

Built-in source-level strategies (`SourceLastWins`, `SourceFirstWins`, `SourceFirstFound`, `SourceRaiseOnConflict`) and field-level strategies (`FieldLastWins`, `FieldFirstWins`, `FieldAppend`, `FieldAppendUnique`, `FieldPrepend`, `FieldPrependUnique`) are now classes implementing public `Protocol`s — `SourceMergeStrategy` and `FieldMergeStrategy` respectively. They live under the new `dature.strategies` package and can be imported as building blocks for custom strategies.

Source-level strategies receive `list[Source]` plus a `LoadCtx` helper, so they can iterate sources themselves, dispatch on source type (e.g. `isinstance(src, EnvSource)`), and decide when to load each one (FIRST_FOUND short-circuit is preserved). Custom strategies compose built-ins — e.g. `SourceLastWins()(files, ctx)` inside an `EnvOverrides` strategy that lays env data strictly on top of files.

The public string API stays: `load(strategy="last_wins", field_merges={F.x: "append"})` continues to work exactly as before. Unknown strategy names now raise `DatureConfigError("invalid merge strategy: '...'. Available: ...")` with the list of valid names.

Internal `MergeStrategyEnum`/`FieldMergeStrategyEnum` enums and the `load_sources`/`LoadedSources` helpers are removed; their logic moved into `LoadCtx.load()`. Callers that imported `dature.merging.strategy` directly need to switch to `dature.strategies`.

Per-step debug logging (`Merge step N`, `State after step N`) and `LoadReport.field_origins` are now driven by a single primary entry point `LoadCtx.merge(source=..., base=..., op=...)`. Built-in strategies and custom strategies use the same call — origins are computed from per-step deltas, so any custom merge logic (including middle-pick / `EnvOverrides`-style with priorities) gets correct `field_origins` for free, without `isinstance` heuristics on the strategy class.
