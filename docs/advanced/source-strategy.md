# Custom Source Strategy

The global `strategy` parameter accepts not only the names from [Merge Strategies](../basic/merging.md#merge-strategies) but also any object implementing the public `SourceMergeStrategy` `Protocol`:

```python
--8<-- "src/dature/loading/merge_runtime.py:source-merge-strategy"
```

The strategy receives the raw `Source` instances (not pre-loaded data) and a `LoadCtx` helper. The primary API for applying a source to the running base is `ctx.merge(source=src, base=base, op=...)` — it loads the source (cached), runs the merge `op` (default `deep_merge_last_wins`), and registers the step so debug logs and `LoadReport.field_origins` are populated correctly. A minimal custom strategy is one loop (as example of SourceLastWins):

```python
--8<-- "src/dature/strategies/source.py:source-last-wins-strategy"
```

Override `op` to plug in your own merge function — e.g. shallow overlay for env on top of files:

=== "Python"

    ```python
    --8<-- "docs/examples/advanced/source_strategy/source_strategy_custom.py:example"
    ```

=== "common_defaults.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_defaults.yaml"
    ```

=== "common_overrides.yaml"

    ```yaml
    --8<-- "docs/examples/shared/common_overrides.yaml"
    ```

`isinstance(src, EnvSource)` (or any other concrete `Source` subclass) lets the strategy dispatch on source type — useful when env variables should override file content rather than merge with it. Pass `skip_on_error=True` to `ctx.merge(...)` (or `ctx.load(...)`) if you want broken sources to be skipped silently regardless of `skip_if_broken` (this is what `SourceFirstFound` does internally).

`ctx.merge` is the single hook — once your strategy funnels every per-source step through it, debug logs (`[Cls] Merge step N ...`, `State after step N: ...`) and `LoadReport.field_origins` are populated automatically; there's no separate registration call to remember.
