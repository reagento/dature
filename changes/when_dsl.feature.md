Added `When` DSL for expressive conditional source conditions.

`When("${VAR}") == "value"`, `.in_(...)`, `.not_in(...)`, and the `&`, `|`, `~` combinators enable OR, NOT, and nested logic that the old dict-based `when=` could not express.

```python
from dature import When

# OR across different templates
when=(When("${APP_ENV}") == "prod") | (When("${REGION}") == "eu")

# NOT
when=~(When("${APP_ENV}") == "prod")

# AND (explicit)
when=(When("${APP_ENV}") == "prod") & When("${REGION}").in_("eu", "us")
```
