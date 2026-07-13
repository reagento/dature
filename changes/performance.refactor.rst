Several performance improvements to build and load, all behaviour-preserving — a valid config
loads faster and lighter, a broken one still surfaces the full aggregated, field-located error.

**Cold build+load (function mode).**

- The happy path now compiles through a trail-free ``DebugTrail.DISABLE`` retort and replays
  through the rich ``DebugTrail.ALL`` retort only when the load fails. adaptix's default
  ``DebugTrail.ALL`` wraps every field in error-tracking codegen — what gives dature its
  field-path errors, but also the bulk of the loader-compilation cost — so a valid config now
  compiles ~25% cheaper and retains less memory. The split is encapsulated behind a
  ``_DualRetort`` facade; call sites and error extraction are unchanged.
- Two module-level FAST retorts are precomputed once at import — one for the string-value recipe
  (``EnvSource``/``EnvFileSource``/CLI/``IniSource``), one for the empty recipe
  (``JsonSource``/``TomlSource``/``YamlSource``/etc.) — and reused for any source with no
  customization, avoiding a per-call ``Retort.extend()``. Detection is by recipe content, not
  class, so user-defined sources benefit automatically; a source with any other recipe falls
  through to the existing ``extend()`` path.

**Warm reuse / hot path (function and decorator mode).**

- Per-schema static reflection (``enum.Flag`` fields, ``Annotated`` default-fallback validators)
  is precomputed once per ``Loader`` instead of calling ``get_type_hints`` on every ``load()``.
- The decorator's re-validation loader is built lazily — only when an explicit
  ``Config(field=...)`` override is passed — and ``Config()`` calls without overrides skip the
  redundant ``merge_fields`` + revalidation pass, since data exiting the load pipeline is already
  validated.
- ``_prepare_for_load()`` is cached and rebuilt only when the active source set changes; the base
  ``Retort`` and the default type-loader providers are module-level singletons; and the ``when=``
  enabled-set computation is skipped entirely when no source uses ``when=``.

**EnvSource.** Values for env vars outside ``prefix`` (or, when set, outside the ``Absolute``
alias set) are no longer decoded from bytes. A new ``_iter_raw_items`` hook on ``FlatKeySource``
filters by key first and only decodes accepted values, so cost scales with the number of matched
variables instead of the whole environment.
