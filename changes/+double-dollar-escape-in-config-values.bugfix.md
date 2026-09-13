A `$$` in a config *data* value immediately before `{@` (e.g. `$${@tag.key}`) no longer leaks
through unresolved as `$${@tag.key}`. Env-var expansion preserved that `$$` unconditionally so a
second, cross-source-ref expansion pass could collapse it to a literal `$` — but data values never
get that second pass, only a source's own constructor arguments and `when=` conditions do. Config
data values now always collapse `$$` to `$`, matching the documented, unconditional escaping
behaviour and the fact that `${@tag.key}` is not interpolated in data values at all, so no escaping
was ever needed there in the first place. Escaping in source constructor arguments (e.g.
`JsonSource(path="$${@env.foo}")`) is unaffected.
