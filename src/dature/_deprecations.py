"""Backward-compatibility shims for names/behaviors renamed or tightened in 1.0.

Keep this module private (``_``-prefixed) — it is not part of the public API.
"""

REMOVAL_NOTICE_15 = "Support will be removed in dature 1.5."

CONFIGURE_DEPRECATION_MESSAGE = (
    "dature.configure() is deprecated and will be removed in dature 1.5. "
    "Use dature.Dature(...) instead:\n\n"
    "  Before: dature.configure(vault={'host': 'x'})\n"
    "          result = dature.load(VaultSource(...), schema=Settings)\n\n"
    "  After:  conf = dature.Dature(vault={'host': 'x'})\n"
    "          result = conf.load(VaultSource(...), schema=Settings)\n\n"
    f"{REMOVAL_NOTICE_15}"
)
