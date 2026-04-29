Error messages now render a caret (``^``) under every visible line of a multi-line value, not just single-line values — so the whole offending block is underlined at a glance. Introduces a new ``CaretSpan(start, end)`` type in ``dature.errors`` and replaces ``SourceLocation.caret: tuple[int, int] | None`` with ``SourceLocation.line_carets: list[CaretSpan] | None`` (parallel to ``line_content``). Per-line caret computation moves from the message renderer into ``Source.resolve_location`` via new classmethods ``_compute_line_carets``, ``_caret_for_key_line``, ``_nonwhitespace_span`` — subclasses can override for format-specific pointing.

As a consequence, ``EnvSource`` and ``DockerSecretsSource`` error output format changes to match the rest of the sources (content line with ``├──`` + caret line + ``└──`` location line):

- ``EnvSource``: ``└── ENV 'APP_PORT' = '0'`` → ``├── APP_PORT=0`` / ``│            ^`` / ``└── ENV 'APP_PORT'``. Multi-line env values are split across separate content lines, each with its own caret.
- ``DockerSecretsSource``: ``├── 0`` → ``├── port = 0`` (content now shows ``secret_name = value`` instead of just the raw value).
