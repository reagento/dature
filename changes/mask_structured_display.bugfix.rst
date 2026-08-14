Fixed error location lines for structured values (JSON objects, YAML mappings, JSON5) being
replaced entirely with ``<REDACTED>``, discarding all key names. Keys are now preserved in the
displayed line and only the individual scalar values are masked: e.g.
``{"host": "localhost", "port": 8080}`` becomes
``{"host": "<REDACTED>", "port": <REDACTED>}`` instead of the previous
``{"host": <REDACTED>``. The caret underline now points at the specific offending field's
value rather than the entire remainder of the line. Multi-line blocks (YAML block mappings,
TOML arrays) now show exactly one caret row on the line that contains the broken field's value,
instead of one row per visible line. Bare/unquoted keys (JSON5 / YAML-in-braces) are also
correctly masked. Values inside arrays (``["web", "web"]``) are masked again too — a
regression introduced alongside the key-preservation fix above had left list elements
untouched.
