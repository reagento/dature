The dict-based `when={"${VAR}": "value"}` syntax has been removed.

Migrate to the `When()` DSL:

| Old | New |
|-----|-----|
| `when={"${ENV}": "prod"}` | `when=When("${ENV}") == "prod"` |
| `when={"${ENV}": ("dev", "local")}` | `when=When("${ENV}").in_("dev", "local")` |
| `when={"${A}": "x", "${B}": "y"}` | `when=(When("${A}") == "x") & (When("${B}") == "y")` |
