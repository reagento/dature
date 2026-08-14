Fixed ``mask_json_value`` failing to mask values nested under a matched secret path: only the
top-level key was checked against ``secret_paths``, so a ``dict`` or ``list`` value under a secret
field (e.g. a nested dataclass named ``auth`` matched by the ``auth`` pattern) recursed with the
same ``secret_paths``, and none of its own keys matched — leaking every value inside it in logs,
error messages, and ``LoadReport``. Matching a secret path now forces masking of every string leaf
in that subtree, regardless of nested key names, while preserving the original ``dict``/``list``
structure.
