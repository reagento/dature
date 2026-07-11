The load hot path is faster and lighter in both function and decorator mode:

- Per-schema static reflection (``enum.Flag`` fields and ``Annotated`` default-fallback
  validators) is now precomputed once per ``Loader`` in ``RetortCache`` instead of calling
  ``get_type_hints`` on every ``load()``.
- The decorator re-validation loader is built lazily — only when an explicit
  ``Config(field=...)`` override is passed — instead of eagerly on every load. Function mode
  and the decorator fast path (``Cfg()``) no longer pay for it.
- The stateless default type-loader providers are built once at import time rather than
  reallocated on every retort build.

Warm reuse (``Loader`` reuse / decorator hot) drops ~21% (e.g. ENV ~99 µs → ~78 µs) and ~10%
on memory (~11.4 KiB → ~10.3 KiB); behaviour is unchanged.
