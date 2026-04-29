Run the pre-finish checklist for the dature project:

1. Run `uv run prek run --all-files` and report any errors
2. Run `uv run pytest -q` and report results
3. Run `git diff --name-only HEAD` — if any `src/` files are changed, check whether a `changes/` fragment exists (`ls changes/`). If not, remind me to create one (format: `echo "Description." > changes/<issue>.<type>` where type is feature/bugfix/doc/refactor/removal/misc)
4. Summarize: what passed, what needs attention before finishing
