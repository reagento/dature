# Naming

Control how dataclass field names map to config keys.

## name_style

Automatically convert between naming conventions. Maps dataclass field names (snake_case) to the convention used in config files.

| Value | Example |
|-------|---------|
| `lower_snake` | `my_field` |
| `upper_snake` | `MY_FIELD` |
| `lower_camel` | `myField` |
| `upper_camel` | `MyField` |
| `lower_kebab` | `my-field` |
| `upper_kebab` | `MY-FIELD` |

```python
--8<-- "examples/docs/naming_name_style.py"
```

## field_mapping

Explicit field renaming using `F` objects. Takes priority over `name_style`:

```python
--8<-- "examples/docs/naming_field_mapping.py"
```

### Multiple Aliases

A field can have multiple aliases — the first matching key in the source wins:

```python
field_mapping={F[Config].name: ("fullName", "userName")}
```

### Nested Fields

Nested fields are supported via `F[Owner].field` syntax on inner dataclasses:

```python
field_mapping={
    F[User].name: "fullName",
    F[User].address: "location",
    F[Address].city: "cityName",
}
```

### Decorator Mode

In decorator mode where the class is not yet defined, use a string:

```python
F["Config"].name  # validation is skipped
```

## prefix

Filters keys for ENV, or extracts a nested object from files:

```python
--8<-- "examples/docs/naming_prefix.py"
```

For file-based sources, `prefix` navigates into nested objects using dot notation:

```python
# config.yaml: { app: { database: { host: localhost, port: 5432 } } }
db = load(LoadMetadata(file_="config.yaml", prefix="app.database"), Database)
```

## split_symbols

Delimiter for building nested structures from flat ENV variables and Docker secrets file names. Default: `"__"`.

```python
--8<-- "examples/docs/naming_split_symbols.py"
```

With environment variables:

```bash
NS_DB__HOST=localhost
NS_DB__PORT=5432
```

The `__` delimiter splits `DB__HOST` into the nested path `db.host`.
