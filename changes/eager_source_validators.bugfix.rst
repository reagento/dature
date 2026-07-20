Invalid ``source.validators`` entries — such as ``V.root(...)`` placed in
``source.validators`` instead of ``root_validators=`` — now raise ``TypeError``
eagerly at ``Loader`` / ``load()`` construction time, regardless of
``cache_engine``. Previously, with ``cache_engine=False`` (the default), the
check was deferred to the first ``load()`` call and the error was wrapped in
``DatureConfigError``.
