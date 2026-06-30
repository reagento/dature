## 0.22.0

### Features

- Added `Absolute` — a `str` subclass for `field_mapping` aliases that bypasses the source `prefix`. Wrap any alias with `Absolute("RAW_KEY")` to match it against the original key regardless of prefix, across all source types (ENV, Docker secrets, file-based). ([#absolute_alias](https://github.com/reagento/dature/issues/absolute_alias))
- Field validators (`Annotated` predicates and `source.validators`) now fire per-source, only for fields that the source actually provided, on the coerced value. Fields that a source did not provide are not validated by that source's pass. Fields that come solely from defaults are validated once at the end on the final object.

  This means an invalid intermediate value raises even if a later source would have overwritten it, and a default value is never falsely validated against a source that did not supply it. ([#per_source_field_validation](https://github.com/reagento/dature/issues/per_source_field_validation))
- Field validators (`Annotated` predicates and `source.validators`) now fire per-source, only for fields that the source actually provided, on the coerced value. Fields that a source did not provide are not validated by that source's pass. Fields that come solely from defaults are validated once at the end on the final object.

  Root validators have been promoted to a schema-level concern: pass them via `root_validators=` on `load()` / `Loader` / `configure()` — see the `schema_root_validators` and `source_root_validators` changelog entries.

  Internal: validating retort is no longer built when a source has no validators (`Annotated` predicates or `source.validators` absent); single-source and multi-source loading each run one field-validation pass per source followed by a single root-retort pass at the end. ([#per_source_validators](https://github.com/reagento/dature/issues/per_source_validators))
- Root validators are now schema-level: pass them via `root_validators=` on `load()`, `Loader`, and `configure()` instead of on the source. They run once on the final merged dataclass instance.

  ```python
  # before
  load(JsonSource(file=..., root_validators=(V.root(check),)), schema=Config)

  # after
  load(JsonSource(file=...), schema=Config, root_validators=(V.root(check),))
  ``` ([#schema_root_validators](https://github.com/reagento/dature/issues/schema_root_validators))
- New `skip_if_missing` parameter on `load()`, `Loader`, and `Source` — silently skips a source whose file does not exist, independently of `skip_if_broken` (parse errors).

  ```python
  # global flag
  load(JsonSource(file="local.json"), EnvSource(), schema=Config, skip_if_missing=True)

  # per-source override
  load(
      JsonSource(file="required.json"),
      JsonSource(file="optional.json", skip_if_missing=True),  # only this source is optional
      schema=Config,
  )
  ``` ([#skip_if_missing](https://github.com/reagento/dature/issues/skip_if_missing))

### Bugfixes

- Fixed exception chaining when `skip_field_if_invalid` exhausts all sources for a required field: the intermediate error was incorrectly set as `__cause__`, causing Python to print a noisy double-group traceback instead of the clean `Config loading errors` format. ([#skip_invalid_error_chain](https://github.com/reagento/dature/issues/skip_invalid_error_chain))

### Docs

- Restructured the documentation:

  - Added `basic/field-paths.md` — single reference page for `F` field path syntax (three forms, usage table, `F` vs `ref` distinction).
  - Added section index pages (`basic/index.md`, `advanced/index.md`) with reading-order tables.
  - Moved `cli_source` and `remote_source` from Basic to Advanced; split each into a concrete-source page and a custom-base-class page (`advanced/cli/argparse.md`, `advanced/cli/custom.md`, `advanced/remote/vault.md`, `advanced/remote/custom.md`). Added CLI / Remote subgroups to the Advanced nav.
  - Merged `source-strategy.md` into `field-strategies.md` and renamed it `merge-strategies.md` (covers both per-field and per-source strategies in one place).
  - Removed the stale `validators.md`; moved the V-DSL predicate table into `basic/validation.md`.
  - Reorganised Advanced nav into four subgroups: Merging & Strategies, Sources, Values, Observability.

  ([#docs_restructure](https://github.com/reagento/dature/issues/docs_restructure))
- • Deleted / moved long text out of example scripts into the docs pages.
  • Kept the docs code samples focused on the real example, with less noise.
  • Updated the docs pages to include the right code blocks from each file.
  • Cleaned up comments, docstrings, and extra setup that was not needed in the rendered examples.
  • Kept the examples runnable and changed the behavior as little as possible. ([#127](https://github.com/reagento/dature/issues/127))

### Refactoring

- Restored `AliasProvider` as a `Provider` subclass; `build_alias_loaders` and the `schema` parameter to `build_base_recipe`/`get_name_mapping_providers` removed. Internal adaptix dependencies are imported from `dature._adaptix_compat`. ([#alias_provider_class](https://github.com/reagento/dature/issues/alias_provider_class))
- Internal: `RetortCache` now computes root-validator providers once at construction time (instead of per-source on every `root_retort()` call), which also validates the `root_validators` argument shape early. The now-redundant standalone `create_root_validator_providers` call and `self._root_validators` attribute on `Loader` have been removed. Dead `root_validators` field on `MergeConfig` removed. ([#loader_init_import](https://github.com/reagento/dature/issues/loader_init_import))
- Removed mutable `_loaded_cache` state from `RemoteSource`. Raw fetch results are now
  forwarded explicitly via `LoadRawResult.loaded_data` and carried in the per-source
  rendering context (alongside `file_content`) rather than stored on the source DTO itself.
  This makes `Source` a pure config DTO with no runtime state.

  Deleted the unused `create_retort`, `create_probe_retort`, and `create_validating_retort`
  factory functions — all retort construction now goes through `RetortCache` which builds
  variants via `Retort.extend()`. ([#remote_loaded_cache](https://github.com/reagento/dature/issues/remote_loaded_cache))
- Moved `resolve_nested_owner` from `expansion.alias_provider` to `field_path`, where it lives alongside `resolve_field_type` (now its thin wrapper). Updated all internal imports accordingly. ([#resolve_nested_owner](https://github.com/reagento/dature/issues/resolve_nested_owner))
- Move retort cache off `Source` into `Loader` via a new `RetortCache` class; `source.retorts` removed. Fix `clone_source` leaking `_loaded_cache` from remote sources. Now keys retorts by stable positional source index instead, so no source-level bookkeeping is needed to survive cloning. ([#retort_cache](https://github.com/reagento/dature/issues/retort_cache))
- Move single-source loading (`load_single`) and the decorator re-validation builder (`build_revalidation`) into `dature.loading.merge` alongside `load_and_merge`, so `Loader` delegates to public helpers only; deduplicate the root/field error-merge into a shared helper; rename internal variables to be clear and unprefixed. ([#separate_load_context_concerns](https://github.com/reagento/dature/issues/separate_load_context_concerns))
- Split `dature.loading.merge` into focused modules; consolidate seven scattered nested-dict path helpers into `dature.nested_dict`; move `validate_all_field_groups` to `dature.merging.field_group` and `get_validator_providers` to `dature.validators.base`; rename internal package `loaders` → `coercion` to resolve the naming clash with the public `Loader` class; fold `field_validation` + `revalidation` into `loading.field_pass` to make the two validation layers distinct by name (`validators/` = define checks, `loading/field_pass.py` = run checks at load time); remove adaptix `Provider`/`loader` re-exports from `dature.coercion`; de-abbreviate all local variable names throughout the loading pipeline. ([#split_loading_modules](https://github.com/reagento/dature/issues/split_loading_modules))

### Removals

- `dature.get_load_report` is renamed to `dature.load_report`.
  The underlying module is also renamed from `dature.load_report` to `dature.report`:

  ```python
  # before
  from dature import get_load_report
  from dature.load_report import LoadReport

  # after
  from dature import load_report
  from dature.report import LoadReport
  ``` ([#report_rename](https://github.com/reagento/dature/issues/report_rename))
- `skip_broken_sources` parameter of `load()` and `Loader` is renamed to `skip_if_broken` and now covers **only parse/config errors** (invalid syntax, malformed files). It no longer silently skips missing files.

  ```python
  # before
  load(..., skip_broken_sources=True)

  # after
  load(..., skip_if_broken=True)  # parse errors only
  load(..., skip_if_missing=True)  # missing files only
  load(..., skip_if_broken=True, skip_if_missing=True)  # both
  ``` ([#skip_broken_rename](https://github.com/reagento/dature/issues/skip_broken_rename))
- `Source.root_validators` has been removed. Use the new `root_validators=` parameter on `load()` / `Loader` / `configure()` instead. See `schema_root_validators` change for migration details. ([#source_root_validators](https://github.com/reagento/dature/issues/source_root_validators))
- `Source`, `CliSource`, `FileSource`, and `RemoteSource` are no longer exported from the top-level `dature` namespace.
  Import them from `dature.sources.base` instead:

  ```python
  from dature.sources.base import Source, CliSource, FileSource, RemoteSource
  ``` ([#sources_base](https://github.com/reagento/dature/issues/sources_base))


## 0.21.0

### Features

- Added `When` DSL for expressive conditional source conditions.

  `When("${VAR}") == "value"`, `.in_(...)`, `.not_in(...)`, and the `&`, `|`, `~` combinators enable OR, NOT, and nested logic that the old dict-based `when=` could not express.

  ```python
  from dature import When

  # OR across different templates
  when=(When("${APP_ENV}") == "prod") | (When("${REGION}") == "eu")

  # NOT
  when=~(When("${APP_ENV}") == "prod")

  # AND (explicit)
  when=(When("${APP_ENV}") == "prod") & When("${REGION}").in_("eu", "us")
  ``` ([#when_dsl](https://github.com/reagento/dature/issues/when_dsl))

### Bugfixes

- fix retort cache collision when two sources of the same type have different
  per-source config (name_style, field_mapping, validators, root_validators).
  Validating and probe retorts are now stored in source.retorts per-instance using
  sentinel keys instead of a Loader-level shared dict keyed by source type — clones
  produced by prepare_sources share the retorts dict via copy.copy shallow copy so
  pre-warmed retorts survive cloning without any extra work.

  PatchContext.validation_loader / error_ctx declared non-optional in protocol
  but initialised to None — calling Cls() in decorator mode before first .load()
  raised TypeError. Protocol updated to reflect real nullability; new_post_init now
  guards on None and runs original __post_init__ without validation in that case. ([#arch-audit-bugfix](https://github.com/reagento/dature/issues/arch-audit-bugfix))
- Concurrent calls to ``configure()`` could silently lose each other's updates
  due to an unguarded read-modify-write. ``_ConfigProxy`` now uses a
  ``threading.RLock`` around ``ensure_loaded``, ``set_instance``, and the full
  body of ``configure()`` so the read + merge + write is atomic. ([#arch-audit-config-thread-safety](https://github.com/reagento/dature/issues/arch-audit-config-thread-safety))
- Missing optional dependency now raises a human-readable ImportError that names
  the missing package and the install command (e.g. ``pip install 'dature[yaml]'``).
  Previously the bare ``ModuleNotFoundError: No module named 'ruamel.yaml'`` gave no
  hint about which dature extra to install. Affects yaml, toml, json5, and vault
  sources. ([#arch-audit-optional-dep-errors](https://github.com/reagento/dature/issues/arch-audit-optional-dep-errors))

### Docs

- Add runtime load() tests for diamond cross-source dependency graphs (H3) and
  two tests for the mypy plugin (H6): one that verifies ``Config()`` is accepted
  without arguments when the plugin is active, and one that confirms mypy reports
  ``call-arg`` errors when the plugin is absent.

  Add a comment to ``load()`` documenting that in decorator mode the cache is
  keyed on the enabled-source set, not on source content — stale data may be
  returned if an env var changes value within the same TTL window. ([#arch-audit-tests](https://github.com/reagento/dature/issues/arch-audit-tests))
- Restructured `conditional_sources` doc: merged "Allowing multiple values", "Combining conditions (AND)", and "OR conditions" into a single tabbed `## Combining conditions` section, one tab per operator (`in_()`, `not_in()`, `&`, `|`, `~`). Fixed stale dict-era wording and broken syntax-reference table links. ([#conditional_sources_doc_tabs](https://github.com/reagento/dature/issues/conditional_sources_doc_tabs))
- Documentation examples have been moved from `examples/docs/` to `docs/examples/` to align with MkDocs conventions and simplify the build configuration. ([#docs_examples_move](https://github.com/reagento/dature/issues/docs_examples_move))

### Refactoring

- Reimplement field-alias expansion on adaptix's public `loader()` + `Chain.FIRST`
  API instead of a custom internal `Provider`, removing all `adaptix._internal`
  imports from `expansion/alias_provider.py`. ([#alias-provider-public-api](https://github.com/reagento/dature/issues/alias-provider-public-api))
- Remove unused topo_order field from CrossRefPlan; keep cycle detection via _topological_sort. ([#arch-audit-dead-code](https://github.com/reagento/dature/issues/arch-audit-dead-code))
- CLI/argparse error locations now show the argument value alongside the flag
  (``--host localhost`` instead of just ``--host``) and place the caret under
  the value, matching the detail level of env and docker-secrets locations.

  Extracted the duplicated "value → line_content + line_carets" arithmetic from
  EnvSource and DockerSecretsSource into a shared ``FlatKeySource._value_line_carets``
  static method, eliminating the two copies of the same multi-line caret loop. ([#arch-audit-error-rendering](https://github.com/reagento/dature/issues/arch-audit-error-rendering))
- Performance improvements and internal API cleanup (no behaviour change):

  - ``make_retort_key(source, type_loaders)`` replaces two private functions
    (``_make_retort_key`` in ``loader`` and ``_retort_cache_key`` in ``retort``).
    ``source.retorts`` is now keyed by source *type* instead of schema type —
    one retort instance per (source-type, type-loaders) pair instead of one per
    (schema, type-loaders).
  - ``create_retort`` / ``create_probe_retort`` accept a pre-built ``base_recipe``
    directly; ``build_base_recipe`` is called once per source in ``Loader.__init__``
    and shared across all three retort builders — was called 2-3× per source.
  - ``Loader.secret_paths`` is forwarded into ``load_and_merge`` so
    ``build_secret_paths`` is not re-run on every multi-source ``.load()``.
  - Pre-warmed ``_probe_retorts`` are threaded through ``load_and_merge → LoadCtx``
    so the merge path reuses the Loader cache instead of creating a new probe
    retort per source per call.
  - ``get_type_hints(load)`` is resolved once via ``@cache`` (``_load_type_hints``)
    instead of three times per CLI run.
  - ``build_secret_paths`` internal cache replaced with ``@lru_cache(maxsize=128)``
    to bound memory when dynamically-created schemas accumulate.

  ([#arch-audit-perf](https://github.com/reagento/dature/issues/arch-audit-perf))
- Fix five stale docstring references to ``multi.py`` in ``merge_runtime.py`` — the module was renamed to ``merge.py`` during a previous loading-layer refactor and these were left behind. ([#arch-dead-multi-refs](https://github.com/reagento/dature/issues/arch-dead-multi-refs))
- Extract ``prepare_loaded_source`` (+ ``PreparedSource``) into
  ``loading/source_loading.py`` as a shared helper for the five identical
  pre-processing steps that ``_do_load_single`` and ``LoadCtx.load`` previously
  duplicated: error_ctx rebuild on nested_conflicts, file_content read, and
  ``apply_skip_invalid`` filtering. Remove the now-dead ``apply_merge_skip_invalid``
  wrapper from ``merge_runtime.py``. ([#arch-dedup-single-multi-load](https://github.com/reagento/dature/issues/arch-dedup-single-multi-load))
- Rename internal modules for clarity: extraction/rendering in errors/, scalars/mask_config in loaders/loading/, validators/aliases,
    type_aliases; formalize Source.check_invariants() hook with Protocol. ([#arch-naming-cleanup](https://github.com/reagento/dature/issues/arch-naming-cleanup))
- Promote `Source._build_line_index` and `Source._compute_line_carets` to public methods.

  Both methods are part of the error-location protocol and were already called
  cross-package from `errors/location.py` with `# noqa: SLF001` suppressions.
  Making them public removes the suppressions and makes the contract explicit for
  authors of custom Source subclasses. ([#arch-public-line-index](https://github.com/reagento/dature/issues/arch-public-line-index))
- Rename internal ``_LoadReport`` to ``_LoadCtxSnapshot`` in ``merge_runtime.py`` to
  distinguish it from the public ``LoadReport`` aggregate. Add ownership docstrings
  to ``report_types.py``, ``load_report.py``, and ``merge_runtime.py`` making the
  three-layer separation explicit. ([#arch-report-types-ownership](https://github.com/reagento/dature/issues/arch-report-types-ownership))
- Move `sources/retort.py` → `loading/retort.py`.

  The retort-building engine (`build_base_recipe`, `create_validating_retort`,
  `transform_to_dataclass`, retort cache keys) had no Source subclass and was
  consumed exclusively by the `loading/` layer. Moving it there makes `sources/`
  a clean leaf package of config-source classes only. ([#arch-retort-move](https://github.com/reagento/dature/issues/arch-retort-move))
- Split ``sources/base.py`` (776 lines) into four focused modules: ``presentation.py``
  (caret/line-range helpers as free functions), ``file_source.py`` (``FileFieldMixin``
  and ``FileSource``), ``flat_key.py`` (``FlatKeySource``), and ``remote.py``
  (``RemoteSource``). Test files mirrored accordingly (``test_file_source.py``,
  ``test_remote.py``). ([#arch-split-base-sources](https://github.com/reagento/dature/issues/arch-split-base-sources))
- Switch `Loader`, `Mediator`, `Provider` to adaptix's public API; funnel remaining
  adaptix internals through a single `_adaptix_compat` shim so an adaptix version
  bump only needs fixing in one place. ([#reduce-adaptix-internal-coupling](https://github.com/reagento/dature/issues/reduce-adaptix-internal-coupling))

### Removals

- The dict-based `when={"${VAR}": "value"}` syntax has been removed.

  Migrate to the `When()` DSL:

  | Old | New |
  |-----|-----|
  | `when={"${ENV}": "prod"}` | `when=When("${ENV}") == "prod"` |
  | `when={"${ENV}": ("dev", "local")}` | `when=When("${ENV}").in_("dev", "local")` |
  | `when={"${A}": "x", "${B}": "y"}` | `when=(When("${A}") == "x") & (When("${B}") == "y")` | ([#when_dict](https://github.com/reagento/dature/issues/when_dict))

### Misc

- [#ci-typing-extensions-compat](https://github.com/reagento/dature/issues/ci-typing-extensions-compat), [#docs_examples_tests](https://github.com/reagento/dature/issues/docs_examples_tests)


## 0.20.0

### Features

- Add cross-source references: ``${@tag.key}`` syntax in source init-fields.
  Sources are loaded in topological order resolved from their inter-dependencies.
  Cycles and tag collisions on referenced tags raise ``DatureConfigError`` with a descriptive message.
  ``$$`` escapes a literal ``$``.

  Cross-ref interpolation is now applied lazily inside the loading pipeline: each source's
  ``load_raw()`` is called exactly once, with ``${@...}`` fields resolved immediately before
  that single call. ``_validate()`` also runs after interpolation, so credential sources like
  ``VaultSource`` see real values in their URL/token fields instead of literal ``${@...}`` strings.

  ``CliSource`` cross-refs now use the same dot-notation as all other sources (``${@cli.db.host}``)
  instead of the flat separator notation (``${@cli.db__host}``).

  When a dependency source is skipped (``skip_if_broken=True`` and the source fails to load),
  its tag contributes an empty dict to the cross-ref context so that ``${@tag.key:-default}``
  fallback expressions on downstream sources still resolve cleanly.

  Exception hierarchy: introduced ``DatureErrorGroup`` as a base ExceptionGroup without ``dataclass_name``;
  ``CrossRefExpandError`` inherits from it directly. ``DatureConfigError`` and all its subclasses
  drop ``__new__`` overrides — construction uses ``__init__`` only. ([#cross_source_refs](https://github.com/reagento/dature/issues/cross_source_refs))
- Add ``when=`` to ``Source``: a declarative condition that enables a source only when all key→value pairs match after template expansion.  Keys support env-var substitution (``${VAR}``, ``${VAR:-default}``) and cross-source references (``${@tag.key}``).  Disabled sources contribute no data to the merge and do not participate in the cross-ref dependency graph — enabling the prod/dev token pattern without ``if``/``else`` around ``load()``. ([#source_when](https://github.com/reagento/dature/issues/source_when))

### Bugfixes

- Unhandled exceptions out of `dature.load()` no longer print a Python traceback header. Non-dature exceptions raised inside dature (`FileNotFoundError`, parser errors, user `__post_init__` failures) are now wrapped at the `Loader.load()` boundary into `DatureConfigError`, so a single `sys.excepthook` (installed on import) renders them via `traceback.print_exception(..., tb=None)`. The same exception classes raised entirely from user code outside dature are unaffected and still print with the normal traceback. ([#clean_stderr_excepthook](https://github.com/reagento/dature/issues/clean_stderr_excepthook))
- Fix field_mapping aliases not matching in sources that normalize key case (EnvSource, EnvFileSource, DockerSecretsSource, IniSource). Aliases such as "DB_PASSWORD" now correctly map to the dataclass field regardless of whether the source lowercases its keys. ([#field_mapping_uppercase](https://github.com/reagento/dature/issues/field_mapping_uppercase))
- ``FieldRef`` is now typed as ``Any`` instead of a fixed union of primitive types.
  Fields in user dataclasses can be of any type (including custom classes), so the previous union was incomplete and caused false mypy errors when using ``F[DataClass].field`` as a ``field_mapping`` key. ([#field_ref_any](https://github.com/reagento/dature/issues/field_ref_any))
- Fix three related `Loader` bugs: decorator footgun (env vars read at import/construction time caused `DatureError` before first `load()`), validation_loader built from init-time last source instead of runtime last source (wrong retort used when lazy `when=` disables the init-chosen source), and `all sources filtered out by when=` raising a bare `DatureError` instead of a `DatureConfigError` group like all other load errors. ([#loader_defer_env](https://github.com/reagento/dature/issues/loader_defer_env))

### Refactoring

- Minor architectural cleanup: ``Loader.load()`` now re-evaluates ``when=`` conditions on every call and auto-clears the cache when the enabled-source set changes; ``DatureConfigError.__init__`` accepts ``BaseException`` items to avoid silent type-ignore; ``Loader._debug`` renamed to public ``Loader.debug``; ``should_skip_broken`` documents that ``when=False`` takes priority over ``skip_if_broken``; ``conditional_sources.md`` gains a section on ``when=``/``skip_if_broken`` precedence. ([#arch_cleanup](https://github.com/reagento/dature/issues/arch_cleanup))
- Unify the single-source and multi-source loading paths through a single `MergeConfig` (removes `prepare_single_source`); split `_do_load_multi` into `_run_merge` + `_validate_merged` for readability; move all env-dependent setup out of `Loader.__init__` into `_prepare_for_load` called on each `.load()`; extract `_make_retort_key` helper and replace `_get_validation_loader` (id-based memoization) with a straightforward `_build_validation_loader`. ([#loader_unify_single_multi](https://github.com/reagento/dature/issues/loader_unify_single_multi))


## 0.19.1

### Bugfixes

- Fix field_mapping aliases not matching in sources that normalize key case (EnvSource, EnvFileSource, DockerSecretsSource, IniSource). Aliases such as "DB_PASSWORD" now correctly map to the dataclass field regardless of whether the source lowercases its keys. ([#field_mapping_uppercase](https://github.com/reagento/dature/issues/field_mapping_uppercase))
- ``FieldRef`` is now typed as ``Any`` instead of a fixed union of primitive types.
  Fields in user dataclasses can be of any type (including custom classes), so the previous union was incomplete and caused false mypy errors when using ``F[DataClass].field`` as a ``field_mapping`` key. ([#field_ref_any](https://github.com/reagento/dature/issues/field_ref_any))


## 0.19.0

### Features

- Add `encoding` field to `FileSource` (and `EnvFileSource`) and a matching `loading.encoding` global default. Default is `None` (Python's `open()` default — platform locale encoding), so existing behavior is unchanged. Set `encoding="utf-8"` on a source or via `configure(loading={"encoding": "utf-8"})` for explicit control.
- Re-export `Provider` and `loader` from `dature.loaders` so custom sources no longer need `from adaptix import ...`.
- ``cache`` parameter on ``dature.load()`` now accepts ``datetime.timedelta`` for TTL-based invalidation (in addition to ``bool``); TTL is bucket-aligned so every class loaded inside the same window invalidates at the exact same instant. Introduced public ``dature.Loader`` class as the explicit carrier of load-time state — including cache. ``dature.load(*sources, schema=Cls, ...)`` is now a thin shortcut for ``Loader(*sources, schema=Cls, ...).load()`` and does not retain cache across calls (throwaway loader). To make caching useful in function mode, construct a ``Loader`` explicitly and reuse the instance. Decorator-mode caching (``@dature.load(...)``) is unchanged. ``LoadingConfig.cache`` accepts the same union type, and ``DATURE_LOADING__CACHE`` can be set to a ``timedelta`` string (e.g. ``0:00:30``) for the same effect.

### Bugfixes

- Fix `read_file_content` in the error formatter to use the source's `encoding` setting. Previously, error location display for `FileSource`/`EnvFileSource` with a non-default encoding (e.g. `cp1251`) would silently fall back to the platform encoding, causing `UnicodeDecodeError` that suppressed line-content from error messages.

### Refactoring

- Internal: comprehensive restructuring of the loading subsystem and import graph. No public API change for end users.

  **Module layout changes:**

  - ``loading/single.py`` removed; per-source report factory moved to ``load_report.py``, logger to ``loader.py``.
  - ``loading/multi.py`` renamed to ``loading/merge.py`` (stripped to merge mechanics only).
  - ``loading/merge_config.py`` deleted.
  - New ``loading/merge_runtime.py`` houses the mutual-annotation triangle (``MergeConfig`` ↔ ``SourceMergeStrategy`` ↔ ``LoadCtx``) together with per-source helpers (``apply_source_init_params``, ``apply_source_config_defaults``, ``resolve_type_loaders``, ``should_skip_broken``, ``resolve_skip_invalid``, ``apply_merge_skip_invalid``).
  - ``loading/source_loading.py`` reduced to ``enrich_skipped_errors``.
  - ``SourceEntry`` / ``FieldOrigin`` extracted to ``report_types.py``; ``LoadReport`` extracted to ``load_report.py`` — breaks the ``report_types ↔ merge_runtime`` cycle.
  - ``SkippedFieldSource`` / ``SourceContext`` moved to ``errors/location.py`` (next to ``ErrorContext``).
  - ``CaretSpan`` / ``LineRange`` / ``SourceLocation`` extracted to ``errors/loc_types.py``, breaking the ``errors.message → errors.exceptions`` dependency.
  - ``FieldValidators`` alias extracted to new ``validators/types.py``; ``types.py`` no longer imports from ``validators``.
  - ``string_value_loaders`` moved from ``sources/retort.py`` to ``sources/base.py``.
  - ``strategies/source.py`` no longer re-exports ``LoadCtx`` / ``SourceMergeStrategy``.

  **Import hygiene:**

  - ``typing.TYPE_CHECKING`` is now banned project-wide (enforced by ruff ``flake8-tidy-imports``); all imports are at module level.
  - All function-scope ``# noqa: PLC0415`` imports removed; remaining circular import cycles broken structurally by the module layout changes above.

  **Potentially breaking for subclasses** (private API): ``_BaseYamlSource._yaml_version()`` now returns ``tuple[int, int]`` instead of ``ruamel.yaml.docinfo.Version``; ``_BaseTomlSource._toml_version()`` annotation changed to ``Literal["1.0.0", "1.1.0"]``.
- Internal: merged `path_finders/` module into the corresponding `sources/` files. No public API change.

  **What changed:**

  - `src/dature/path_finders/` removed entirely (was internal, never exported).
  - `src/dature/_descriptors.py` (`classproperty`) removed — no longer needed.
  - `Source.path_finder_class` class variable removed.
  - New `Source._build_line_index(content: str) -> dict[tuple[str, ...], LineRange] | None` method added.
    Default returns `None` (no diagnostics). Format sources override it to return a line map.
  - Line-lookup logic for yaml, toml, json, json5, ini now lives in the same file as the corresponding `Source` class (e.g. `sources/yaml_.py` contains `_build_yaml_line_map` and `_walk_yaml_mapping`).
  - `_find_parent_line_range` in `Source` updated to accept a dict instead of a `PathFinder` instance.
  - Tests from `tests/path_finders/` moved to `tests/sources/test_<fmt>_line_index.py`.

  **For custom Source subclasses** (private API): if you previously set `path_finder_class` on a custom source, override `_build_line_index` instead. Return a `dict[tuple[str, ...], LineRange]` mapping dotted key paths to line ranges, or `None` to disable diagnostics.


## 0.18.0

### Features

- Add ``dature`` CLI with ``inspect`` (prints the load report) and ``validate`` (exits 0 on success, 1 on validation failure) subcommands. Sources are passed as ``--source type=dature.JsonSource,file=config.json`` (Docker-style key=value, ``\,`` and ``\=`` escape separators in values), and the schema as ``--schema myapp.config:Settings``. Global flags mirror ``load()`` and are generated from its signature.

  Add ``ArgparseSource`` and the abstract ``CliSource`` base — a Source for loading command-line arguments into a dataclass. ``ArgparseSource`` takes a user-built ``argparse.ArgumentParser`` (the parser reads ``sys.argv`` itself; supports any depth of subparsers, mapped to nested fields). Bool flags always feed into the result; non-bool args only when explicitly passed, so CLI safely composes with file/env sources via ``load()``. ``CliSource`` is the extension point for click/typer/custom parsers — implement ``_parse_argv()`` and you're done. ([#84](https://github.com/reagento/dature/issues/84))
- Add ``RemoteSource`` (abstract base for Sources that fetch from remote services) and the first concrete remote: ``VaultSource`` for HashiCorp Vault. Supports KV v1 and KV v2, token and AppRole authentication, optional Vault Enterprise namespace. Connection settings (url, credentials, mount_point, kv_version) can be set per-instance, via ``dature.configure(vault={...})``, or via ``DATURE_VAULT__*`` env vars; instance-level fields take precedence. Install via ``pip install dature[vault]``. Integration tests requiring a running Vault container are gated behind the ``integration`` pytest marker (excluded from the default ``pytest`` run; run via ``pytest -m integration`` with ``testcontainers[vault]`` installed).

### Bugfixes

- Fix ``LoadReport.sources[*].file_path`` and ``LoadReport.field_origins[*].source_file`` to contain a path string rather than the ``repr()`` of a ``pathlib.Path`` (e.g. ``"PosixPath('...')"``).

  Fix ``dature ... --secret-field-names X`` crashing with ``TypeError: unhashable type: 'list'``. The CLI schema declares ``secret_field_names`` as ``list[str]`` (argparse ``action="append"`` produces a list), but ``load()`` expects ``tuple[str, ...]`` and uses it as part of a dict cache key. ``build_load_kwargs_from_dataclass`` now coerces the list back to a tuple at the load() boundary for any param whose ``load()`` annotation is tuple-shaped.

  Fix ``CliSource`` error messages displaying flag names in upper case (e.g. ``--DB--HOST``). The base ``FlatKeySource`` uppercases via ``_build_var_name`` because that matches env-var convention (``APP_DB_HOST``); ``CliSource`` now overrides ``_build_var_name`` to preserve case, so both ``NestedConflict.used_var`` (built during nested-conflict detection) and the flag name rendered in error messages remain in their original case (``--db--host``).

  ``CliSource`` (and therefore ``ArgparseSource``) now defaults ``expand_env_vars`` to ``"disabled"``. The shell has already expanded ``$VAR`` before values reach Python; re-expanding silently turned quoted literals like ``--password '$ecret'`` into empty strings. Users who want CLI values re-expanded can opt in by passing ``expand_env_vars="default"`` (or ``"empty"`` / ``"strict"``) explicitly.

  Fix mixed path separators on Windows when a ``Path`` is passed to a file-based ``Source`` and contains an ``$ENV_VAR`` whose value uses ``/``. ``Toml11Source(file=Path("$DATURE_DIR") / "config.toml")`` with ``DATURE_DIR=/etc/app`` previously produced ``/etc/app\config.toml``; ``expand_file_path`` now re-normalizes through ``pathlib.Path`` when the input was a ``Path``, yielding ``\etc\app\config.toml`` on Windows and ``/etc/app/config.toml`` on POSIX. ``str`` inputs are still returned verbatim so user-chosen separators are preserved. ([#84](https://github.com/reagento/dature/issues/84))
- Fix ``RemoteSource.resolve_location`` ignoring the source's ``prefix``: error messages for prefixed sources (e.g. ``VaultSource(prefix="app", ...)``) used to show only the field key without the rendered value, because ``_lookup_loaded`` was called with the schema-side ``field_path`` directly while ``_loaded_cache`` holds the raw pre-prefix data.
- Fix single-source ``dature.load(source, schema=...)`` (and the ``@load(source)`` decorator) ignoring ``dature.configure(...)`` and ``DATURE_*`` env defaults — only the multi-source path was running ``apply_source_config_defaults``. Notably affects ``VaultSource`` users who relied on global ``vault`` configuration with a single source.

### Docs

- Add documentation for ``RemoteSource`` and the contract for plugging in custom remote sources, with ``VaultSource`` as a worked example. Examples are runnable end-to-end against a live Vault container in the integration suite.

### Refactoring

- ``dature`` CLI now parses its own arguments through ``ArgparseSource``: the schema it loads into is built at runtime from the signature of ``load()`` via ``dataclasses.make_dataclass``, so CLI flags stay in sync with the public API automatically. ``main()`` no longer accepts an ``argv`` parameter — like ``ArgparseSource`` itself, it reads ``sys.argv`` directly. Bool actions registered with ``default=None`` are now suppressed from ``ArgparseSource`` output (treated as "unset", same as non-bool flags), so absence on the CLI falls back to the schema/dataclass default rather than emitting a literal ``None``. ([#84](https://github.com/reagento/dature/issues/84))

### Misc

- Move ``types-hvac`` out of the runtime ``vault`` extra into a new ``type-stubs`` extra so production installs of ``dature[vault]`` no longer pull typing stubs. mypy/pyright users opt in with ``pip install dature[vault,type-stubs]``.


## 0.17.1

### Bugfixes

- ``import dature`` no longer pulls in the optional ``json5`` package. Previously, ``dature.loaders.json5_`` imported ``json5.JsonIdentifier`` at module load time, so any project that depended on dature without the ``[json5]`` extra crashed with ``ModuleNotFoundError: No module named 'json5'`` on the very first ``from dature import ...``. The annotation is now resolved lazily under ``TYPE_CHECKING``.


## 0.17.0

### Features

- Set default ``file`` parameter to ``".env"`` in :class:`.EnvFileSource`. The class can now be instantiated without arguments: ``EnvFileSource()`` loads from ``.env`` in the current working directory. ([#envfile-default-dotenv](https://github.com/reagento/dature/issues/envfile-default-dotenv))
- Added automatic config file search in standard system locations.

  All `FileSource` subclasses (YamlSource, JsonSource, TomlSource, IniSource, EnvFileSource) now search for config files in:
  - `~/.config/` (Linux/macOS)
  - `/etc/` (Linux)
  - `/etc/xdg/` (Linux)
  - `%APPDATA%/` (Windows)

  Search is enabled by default. Can be configured globally via `dature.configure(loading={...})` or per-source via `search_system_paths` and `system_config_dirs` parameters.
- Added the ``V`` DSL for validation predicates: ``Annotated[int, (V >= 1) & (V <= 65535)]``, ``Annotated[str, V.len() >= 3]``, ``Annotated[list[str], V.unique_items() & V.each(V.len() >= 3)]``. Predicates compose via ``&``, ``|``, and ``~``. ``V.each(...)`` validates each element and reports the failing index in the field path (``tags.2``). ``V.check(func, error_message=...)`` is the escape hatch for arbitrary user predicates. ``V.root(func, error_message=...)`` replaces ``RootValidator`` for cross-field checks. Applying a predicate to an incompatible type (e.g. ``V.len()`` on ``int``) now raises ``ValidatorTypeError`` eagerly, before any configuration data is read.
- All concrete source classes (``EnvSource``, ``JsonSource``, ``Yaml11Source``, ``Yaml12Source``, ``Toml10Source``, ``Toml11Source``, ``IniSource``, ``Json5Source``, ``EnvFileSource``, ``DockerSecretsSource``, ``FileSource``) are now exported from ``dature`` directly.
- Environment variables in `Source(file=...)` are now expanded automatically in strict mode. Both directory paths (`$CONFIG_DIR/config.toml`) and file names (`config.$APP_ENV.toml`) are supported.
- Error messages for ``EnvSource`` and ``DockerSecretsSource`` now include the actual field value. ``EnvSource`` shows ``ENV 'VAR_NAME' = 'value'``; ``DockerSecretsSource`` shows the file content before the secret file path. Secret fields are not affected — their values remain hidden. The caret in error messages now points to the specific field's value within a JSON object, rather than the last occurrence of the same string.
- Error messages now render a caret (``^``) under every visible line of a multi-line value, not just single-line values — so the whole offending block is underlined at a glance. Introduces a new ``CaretSpan(start, end)`` type in ``dature.errors`` and replaces ``SourceLocation.caret: tuple[int, int] | None`` with ``SourceLocation.line_carets: list[CaretSpan] | None`` (parallel to ``line_content``). Per-line caret computation moves from the message renderer into ``Source.resolve_location`` via new classmethods ``_compute_line_carets``, ``_caret_for_key_line``, ``_nonwhitespace_span`` — subclasses can override for format-specific pointing.

  As a consequence, ``EnvSource`` and ``DockerSecretsSource`` error output format changes to match the rest of the sources (content line with ``├──`` + caret line + ``└──`` location line):

  - ``EnvSource``: ``└── ENV 'APP_PORT' = '0'`` → ``├── APP_PORT=0`` / ``│            ^`` / ``└── ENV 'APP_PORT'``. Multi-line env values are split across separate content lines, each with its own caret.
  - ``DockerSecretsSource``: ``├── 0`` → ``├── port = 0`` (content now shows ``secret_name = value`` instead of just the raw value).
- Made merge strategies pluggable via a `Protocol`-based class API.

  Built-in source-level strategies (`SourceLastWins`, `SourceFirstWins`, `SourceFirstFound`, `SourceRaiseOnConflict`) and field-level strategies (`FieldLastWins`, `FieldFirstWins`, `FieldAppend`, `FieldAppendUnique`, `FieldPrepend`, `FieldPrependUnique`) are now classes implementing public `Protocol`s — `SourceMergeStrategy` and `FieldMergeStrategy` respectively. They live under the new `dature.strategies` package and can be imported as building blocks for custom strategies.

  Source-level strategies receive `list[Source]` plus a `LoadCtx` helper, so they can iterate sources themselves, dispatch on source type (e.g. `isinstance(src, EnvSource)`), and decide when to load each one (FIRST_FOUND short-circuit is preserved). Custom strategies compose built-ins — e.g. `SourceLastWins()(files, ctx)` inside an `EnvOverrides` strategy that lays env data strictly on top of files.

  The public string API stays: `load(strategy="last_wins", field_merges={F.x: "append"})` continues to work exactly as before. Unknown strategy names now raise `DatureConfigError("invalid merge strategy: '...'. Available: ...")` with the list of valid names.

  Internal `MergeStrategyEnum`/`FieldMergeStrategyEnum` enums and the `load_sources`/`LoadedSources` helpers are removed; their logic moved into `LoadCtx.load()`. Callers that imported `dature.merging.strategy` directly need to switch to `dature.strategies`.

  Per-step debug logging (`Merge step N`, `State after step N`) and `LoadReport.field_origins` are now driven by a single primary entry point `LoadCtx.merge(source=..., base=..., op=...)`. Built-in strategies and custom strategies use the same call — origins are computed from per-step deltas, so any custom merge logic (including middle-pick / `EnvOverrides`-style with priorities) gets correct `field_origins` for free, without `isinstance` heuristics on the strategy class.
- ``LoadingConfig.system_config_dirs`` now holds the full platform-search policy directly: a ``Mapping[str, Iterable[Path | str]]`` keyed by ``sys.platform`` with XDG-compliant defaults. String entries expand ``$VAR``/``${VAR}``/``${VAR:-default}`` and ``~``; each entry is split by ``os.pathsep`` after expansion, so ``$XDG_CONFIG_DIRS=/a:/b`` yields two directories. Undefined environment variables without a fallback are skipped and a warning is logged. New public type alias ``dature.types.SystemConfigDirsArg``.

### Bugfixes

- Fixed ``apply_source_init_params`` leaking a stale ``FileFieldMixin._resolved_file_path`` cache: priming the cache (e.g. via ``repr(source)``) before ``load(...)`` no longer prevents ``search_system_paths`` / ``system_config_dirs`` overrides from taking effect.
- Fixed attribute name typo (``filecontent`` → ``file_content``) in ``raise_on_conflict`` merge strategy that caused ``AttributeError`` when conflicting fields were detected.
- ``EnvFileSource`` now honors ``search_system_paths`` and ``system_config_dirs`` (previously the system-path search was bypassed for ``.env`` files).
- ``load()`` no longer emits the "Merge-related parameters have no effect with a single source" warning when ``strategy`` is left at its default. Detection is now decoupled from the specific default strategy value — the warning fires when the user explicitly passes ``strategy``, regardless of which strategy was passed (the previous string-equality check incorrectly treated class-form defaults like ``SourceLastWins()`` as non-default).
- ``strategy="first_found"`` now correctly limits ``field_merges``, ``field_groups``, and the merged source's type loaders / error context to the single source it selected. Previously, combining ``first_found`` with ``field_groups`` triggered an internal pre-load that broke the strategy's documented short-circuit and silent-skip semantics — broken sources could surface errors instead of being skipped, validation errors could be attributed to the wrong file, and ``field_merges`` could aggregate over sources the strategy never picked.

### Docs

- Added a new "Loading" page to the Getting Started section that walks through common load-time errors (missing file, malformed source, type mismatch, missing required field, multiple errors) with their actual stderr output, plus a `skip_if_broken` recovery example.
- Improved documentation for Caching, Merge Rules, Configure, Custom Types, and Field Groups sections.
- Updated documentation to reflect the renaming of ``split_symbols`` to ``nested_sep`` parameter across all affected pages.
- Validation docs now use real runnable examples for every source format in the Error Format section (YAML, JSON, JSON5, TOML, INI, ENV, ENV file, Docker Secrets), plus new examples for multi-line and dataclass-typed values. Removed duplicated "Error Messages" section from the Introduction page.

### Refactoring

- Built-in validators (`Ge`, `Le`, `Gt`, `Lt`, `MinLength`, `MaxLength`, `RegexPattern`, `MinItems`, `MaxItems`, `UniqueItems`) now accept `value` as a positional argument: `Ge(1)` instead of `Ge(value=1)`. `RootValidator` now accepts `func` as a positional argument: `RootValidator(check)` instead of `RootValidator(func=check)`. `error_message` remains keyword-only in all validators.
- Deduplicated ``_find_nested_dataclasses`` into shared ``type_utils.find_nested_dataclasses``.
- Error message formatting helpers extracted from ``dature.errors.exceptions`` into a new ``dature.errors.message`` module. Exception classes now contain only data and delegate rendering to ``format_location`` / ``format_path``.
- Examples for docs in `examples/` dir now has `line-length = 80`
- Extracted retort factory methods from ``Source`` into free functions in ``sources/retort.py``. ``transform_to_dataclass`` is now a free function.
- Extracted shared ``resolve_mask_secrets`` logic from ``single.py`` and ``multi.py`` into ``loading/common.py``.
- Internal type hints now use `MergeStrategyEnum`/`FieldMergeStrategyEnum` instead of `MergeStrategyName`/`FieldMergeStrategyName` Literal aliases. Public API type hints remain unchanged.
- Moved ``_string_value_loaders`` and adaptix runtime imports out of ``dature.sources.base`` into ``dature.sources.retort``. ``string_value_loaders`` is now importable from ``dature.sources.retort``. Public API is unchanged.
- Recommended import style changed from `from dature import load, Source` to `import dature` with access via `dature.load()`, `dature.Source()`.
- Renamed ``_MergeConfig`` to ``MergeConfig``.
- Renamed ``display_name`` to ``format_name`` and ``display_label`` to ``location_label`` across all source classes and error types.
- Renamed ``metadata``/``source_meta`` parameters to ``source`` throughout the loading module.
- Renamed internal package ``sources_loader`` to ``sources`` (source classes) and ``loaders`` (type conversion). All public imports from ``dature`` are unchanged.
- Simplified ``config_paths``: ``get_system_config_dirs`` is now a generator yielding directories in priority order, private platform helpers inlined, internal ``iter_config_paths`` removed. ``find_config`` is the sole search primitive; ``sources.base`` uses it via a cached ``_resolved_file_path`` property (no more repeated filesystem probes on a single source). ``FileSource._load`` handles streams explicitly.
- Source user-facing attributes are no longer mutated during ``load()``. Load-level params are injected into source fields via ``_apply_source_init_params()`` before loading. ``MergeConfig`` is split into merge-specific settings and a ``SourceParams`` dataclass holding per-source defaults. ``load_raw()`` reads directly from ``self`` without parameters. The ``retorts`` cache is still populated lazily during loading.
- `Merge` class has been removed. Use `load()` with multiple `Source` arguments instead.
- `Source(file_=...)` has been renamed to `Source(file=...)`.
- ``SourceRaiseOnConflict`` now performs its conflict-detection pass internally instead of relying on ``multi.py``. The generic loader is fully strategy-agnostic; custom strategies can replicate the same behaviour via ``raise_on_conflict(ctx.loaded_raw_dicts(), ctx.loaded_source_ctxs(), ctx.dataclass_name, field_merge_paths=ctx.field_merge_paths)``. ``LoadCtx`` now exposes ``dataclass_name`` and ``field_merge_paths`` as public attributes for this purpose. As a side effect, when ``raise_on_conflict`` is combined with ``field_groups`` and both validations would fail, ``MergeConflictError`` now surfaces before ``FieldGroupError`` (previously the order was reversed); both errors require user action either way.
- ``apply_source_init_params`` is now invoked exactly once per source — inside ``MergeConfig.__post_init__`` — instead of being re-applied at each downstream call site (retort warmup, validating retort, ``LoadCtx.load``). The function moved to ``loading/merge_config.py``; ``MergeConfig.sources`` now stores prepared sources after construction.
- `configure()` now accepts dicts instead of dataclass instances: `masking={"mask": "***"}`, `error_display={"max_visible_lines": 5}`, `loading={"debug": True}`, `type_loaders={MyType: my_loader}`.

### Removals

- Removed `FieldGroup` dataclass from public API. Pass `field_groups` as `tuple[tuple[F[Config].field, ...], ...]` instead.
- Removed `MergeRule` dataclass from public API. Pass `field_merges` as `dict` mapping `F[Config].field` to a strategy string or callable instead.
- Removed `MergeStrategy` and `FieldMergeStrategy` enums from public API. Use string literals instead: `"last_wins"`, `"first_wins"`, `"first_found"`, `"raise_on_conflict"` for merge strategies; `"first_wins"`, `"last_wins"`, `"append"`, `"append_unique"`, `"prepend"`, `"prepend_unique"` for field merge strategies.
- Removed `TypeLoader` dataclass from public API. Pass `type_loaders` as `dict[type, Callable]` instead.
- Removed ``LoaderProtocol`` from ``dature.protocols``. Source classes now handle loading internally.
- Removed ``dature.config_paths.get_system_config_dirs``. System search directories are now fully defined in ``LoadingConfig.system_config_dirs`` (accessible as ``dature.config.loading.system_config_dirs`` at runtime).
- Removed `secret_field_names` and `mask_secrets` from the `Source` dataclass. Pass them to `dature.load()` instead — passing them to a `Source` constructor now raises `TypeError`.
- Removed the per-class validator API (``Ge``, ``Gt``, ``Lt``, ``Le``, ``MinLength``, ``MaxLength``, ``RegexPattern``, ``MinItems``, ``MaxItems``, ``UniqueItems``, ``RootValidator``) and ``ValidatorProtocol``. All validation must now go through ``V`` — see the `+v-dsl.feature` fragment. Default error messages for length-based predicates changed from ``"Value must have at least N characters"`` / ``"Value must have at least N items"`` to the unified ``"Value length must be greater than or equal to N"`` (override via ``.with_error_message(...)`` if needed).
- Renamed ``split_symbols`` parameter to ``nested_sep`` in :class:`.FlatKeySource` and all subclasses (``EnvSource``, ``EnvFileSource``, ``DockerSecretsSource``). The old parameter name is no longer supported.

### Misc

- Added unit tests for ``loading/context``, ``loading/source_loading``, ``masking/detection``, ``validators/base``, ``loaders/common``, ``loaders/base``.


## 0.16.0

### Features

- Reworked masking configuration: replaced `mask_char`, `min_visible_chars`, `min_length_for_partial_mask`, and `fixed_mask_length` with `mask`, `visible_prefix`, and `visible_suffix`. Default masking now fully redacts values as `<REDACTED>` instead of showing partial content.

### Docs

- Extracted all inline Python code blocks from docs into executable example files with assertions. Affected pages: `masking.md`, `why-not-pydantic-settings.md`, `why-not-dynaconf.md`, `why-not-hydra.md`.

### Misc

- Added coverage for test coverage tracking in CI.


## 0.15.3

### Features

- `Merge` now accepts `sources` as a positional argument: `Merge(Source(...), Source(...))`. ([#merge-positional-sources](https://github.com/reagento/dature/issues/merge-positional-sources))


## 0.15.2

### Bugfixes

- Fixed placeholder values in ``ByteSize`` and ``PaymentCardNumber`` examples that prevented them from running.

### Docs

- Fixed incorrect code examples in comparison docs (``Merge`` keyword args, ``MergeStrategy`` enum values, validator import paths). Replaced ``docs/changelog.md`` with a symlink to root ``CHANGELOG.md``.


## 0.15.1

### Features

- Switched to hatch-vcs for dynamic versioning from git tags and towncrier for changelog management. Removed PAT token dependency from all CI workflows.


# Changelog

## Unreleased

## 0.15.0

### Improvements
- Refactored and renamed the `load_metadata` function for better clarity and consistency.

### Docs
- Updated documentation across multiple files to reflect changes related to the `load_metadata` function.

## 0.14.4

### Docs
- Improved documentation for the "Why not Pydantic Settings" section.
- Updated the configuration of the documentation site.

## 0.14.3

### Docs
- Fixed issues in the documentation for improved clarity and accuracy.
- Updated the configuration for Read the Docs integration in the documentation.
- Updated the JavaScript configuration for Read the Docs.

## 0.14.2

### Fixes
- Corrected issues in the documentation related to JavaScript integration.

## 0.14.1

### Docs
- Updated documentation for clarity and consistency.
- Improved the CI workflow for better integration with documentation generation.
- Enhanced stylesheets for improved readability in documentation.
- Refactored documentation generation scripts for better maintainability.
- Resolved various issues in the documentation.

## 0.14.0

### Improvements
- Refactored error handling in the exceptions module to provide clearer messages.
- Enhanced the sources loader to improve performance and reliability.
- Updated validation examples to demonstrate new features and best practices.
- Improved error handling in the loading module to prevent crashes on invalid inputs.

### Fixes
- Resolved issues with error reporting in the validation module.
- Fixed bugs in the masking examples to ensure accurate functionality.
- Corrected various test cases to improve coverage and reliability.
- Addressed errors in the source loading process to enhance stability.
- Fixed errors related to loading configurations from different sources.

## 0.13.0

### Features
- Introduced a new strategy for configuration loading.

### Improvements
- Enhanced the `int_from_string` function to correctly cast boolean values to integers.
- Improved documentation for advanced configuration options.

### Fixes
- Updated the README to reflect recent changes and improvements.
- Addressed comments from Devin regarding code clarity and documentation.

## 0.12.4

### Fixes
- Ensured JSON5 support is now correctly required in the configuration loader.
- Resolved issues related to loading configurations from JSON5 files.

## 0.12.3

### Improvements
- Refactored the strict retort functionality for enhanced performance.
- Added a fallback mechanism for Read the Docs (RTD) to improve documentation accessibility.

### Fixes
- Resolved issues in various source loader files to ensure better compatibility and functionality.

## 0.12.2

### Improvements
- Removed duplicate error messages for better clarity.
- Eliminated unnecessary traceback information to streamline error reporting.

### Fixes
- Fixed the Read the Docs configuration in the CI workflow to ensure proper documentation generation.

## 0.12.1

### Improvements
- Enhanced the changelog generation process to ensure accurate updates.
- Updated documentation to include support for `timedelta` as a valid type.
- Resolved security issues to improve overall safety.

### Docs
- Corrected documentation tags for clarity and consistency.

### Features
- Added logging functionality to `dature`.
- Added Docker Secrets loader.
- Added `SecretStr`, `PaymentCardNumber`, and `ByteSize` special field types.
- Added secret masking in error messages (by field name and heuristic detection).
- Added ENV variable expansion in config values.
- Added field alias provider for flexible field name mapping.
- Added `configure()` for global masking, error display, and loading settings.
- Added `F` field path objects with field mapping support.
- Added field group support for merge rules.
- Added custom merge functions and merge strategies (`append`, `prepend`, `first_wins`, etc.).
- Added `skip_invalid` and `skip_broken` merge options (global and per-source).
- Added mypy plugin.

### Improvements
- Restructured source code into subpackages: `errors/`, `expansion/`, `fields/`, `loading/`, `masking/`, `merging/`.
- Restructured tests to mirror `src/` layout.
- Improved path finders for YAML, TOML, JSON, JSON5, and INI formats.
- Improved error formatting with source location context.
- Improved source loader base with better type safety.
- Improved ENV loader with strip and type handling.
- Skipped lint/test jobs on tag push in CI (already verified on main push).
- Improved CI configurations for better stability and reliability.

### Fixes
- Fixed various issues in the CI configuration.
- Resolved multiple bugs affecting functionality and stability.

### Docs
- Added documentation site (MkDocs + Material) with full coverage: getting started, features, advanced topics, API reference.
- Added `CHANGELOG.md` with AI-generated entries on PR creation.
- Added social cards, minify, 8-bit themed headings, and custom color scheme to docs.
- Added changelog workflow: AI generates changelog entries per PR, release job extracts them for GitHub Releases.
- Added CI support for tag push: `pypi-publish`, `github-release`, and `trigger-rtd` now run on tag events.
- Added `trigger-rtd` job supporting both `latest` (main) and `stable` (tag) RTD builds.
- Added version-bump, dependency-review, scorecard, and docs CI workflows.
- Added dependabot configuration.
- Added CODEOWNERS and SECURITY.md.
- Added comprehensive examples for all features.
- Slimmed down `README.md` in favor of documentation site.

