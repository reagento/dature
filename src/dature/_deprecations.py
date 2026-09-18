"""Backward-compatibility shims for names/behaviors renamed or tightened in 1.0.

Keep this module private (``_``-prefixed) — it is not part of the public API.
"""

REMOVAL_NOTICE_16 = "Support will be removed in dature 1.6."

CONFIG_DIRS_RENAME_MESSAGE = (
    "system_config_dirs is deprecated and will be removed in dature 1.6. Use config_dirs instead:\n\n"
    "  Before: system_config_dirs=('/etc/myapp',)\n"
    "  After:  config_dirs=('/etc/myapp',)\n\n"
    f"{REMOVAL_NOTICE_16}"
)

SEARCH_SYSTEM_PATHS_MESSAGE = (
    "search_system_paths is deprecated and will be removed in dature 1.6. "
    "Whether search happens is now expressed by config_dirs itself:\n\n"
    "  Before: search_system_paths=False\n"
    "  After:  config_dirs=()\n\n"
    f"{REMOVAL_NOTICE_16}"
)
