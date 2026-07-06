Removed ``encoding_for_errors()`` from ``FileSourceProtocol``; use the
``encoding`` attribute directly instead.  Moved ``build_line_index()`` from
``SourceProtocol`` to ``FileSourceProtocol`` — custom sources that are not
file-based no longer need to implement it.
