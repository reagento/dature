Documented that `ArgparseSource` is the one source that does not translate its own errors
into a readable, field-path-carrying exception: a missing required CLI argument raises
`SystemExit` straight out of `parser.parse_args()` instead, matching normal CLI behavior. No
behavior change — `SourceProtocol.load_raw()` and `ArgparseSource`'s docstring now say so
explicitly.
