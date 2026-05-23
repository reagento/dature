Internal: comprehensive restructuring of the loading subsystem and import graph. No public API change for end users.

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
