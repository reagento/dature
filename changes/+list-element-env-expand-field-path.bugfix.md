A missing environment variable inside a list element (e.g. `hosts: ["ok", "$MISSING"]`) now
reports `field_path` as `["hosts", "1"]` instead of `["hosts"]`, so `expand_env_vars="strict"`
errors point at the offending list index rather than the whole list.
