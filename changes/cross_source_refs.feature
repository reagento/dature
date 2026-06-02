Add cross-source references: ``${@tag.key}`` syntax in source init-fields.
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
drop ``__new__`` overrides — construction uses ``__init__`` only.
