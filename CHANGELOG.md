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

