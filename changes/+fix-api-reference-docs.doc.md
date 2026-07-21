Fixed numerous inaccuracies in ``docs/api-reference.md``: wrong parameter types/defaults (``root_validators``, ``nested_resolve_strategy``), a fabricated ``Loader.invalidate()`` method, a stale Validators section rewritten for the current ``V`` DSL, missing ``ArgparseSource``/``VaultSource`` and ``VaultConfig`` documentation, and missing exception classes (``DatureErrorGroup``, ``ValidatorTypeError``, ``ConfigEnvVarExpandError``, ``CrossRefError``/``CrossRefExpandError``).

Fixed parameter tables in ``docs/introduction.md`` that no longer matched the ``Source``/``FileSource`` dataclass fields.

Fixed several ``--8<--`` example includes that rendered empty due to broken indentation or missing ``[start:example]``/``[end:example]`` markers, in ``docs/basic/naming.md``, ``docs/basic/masking.md``, ``docs/advanced/custom_sources.md``, ``docs/advanced/nested-resolve.md``, and ``docs/basic/validation.md``.
