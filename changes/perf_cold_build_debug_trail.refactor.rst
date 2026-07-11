Cold build+load (function mode) is ~25% faster and lighter. adaptix's default
``DebugTrail.ALL`` wraps every field in error-tracking codegen — what gives dature its
field-path errors, but also the bulk of the loader-compilation cost. ``RetortCache`` now loads
the happy path through a trail-free ``DebugTrail.DISABLE`` retort and replays the load through
the rich (``DebugTrail.ALL``) retort only when it fails, so a valid config compiles ~25% cheaper
(e.g. ENV ~1.6 ms → ~1.2 ms) and retains less memory (~31 KiB → ~22 KiB per build, now below
pydantic-settings), while a broken config still surfaces the full aggregated, field-located error.

The fast/rich split is fully encapsulated behind ``RetortCache.final_retort`` / ``field_pass``
(a ``_DualRetort`` facade) — call sites and error extraction are unchanged. The ``skip_invalid_fields``
probe stays on the rich retort (it uses load errors as per-field control flow).
