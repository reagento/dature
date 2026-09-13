`dature.expansion.env_expand` merges the two parallel `$VAR`/`${VAR}`/`%VAR%` expanders that
previously existed side by side — one for `"default"` mode, one for `"empty"`/`"strict"` — into a
single `_EnvExpander`. They differed only in what to do when a variable is missing; that policy is
now one method (`_on_missing`) instead of duplicated regex-callback bodies. No observable behavior
changes.
