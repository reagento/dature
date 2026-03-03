# Validation

dature supports multiple validation approaches: `Annotated` type hints, root validators, metadata validators, custom validators, and standard `__post_init__`.

## Annotated Validators

Declare validators using `typing.Annotated`:

```python
--8<-- "examples/docs/validation_annotated.py"
```

### Available Validators

**Numbers** (`dature.validators.number`):

| Validator | Description |
|-----------|-------------|
| `Gt(value=N)` | Greater than N |
| `Ge(value=N)` | Greater than or equal to N |
| `Lt(value=N)` | Less than N |
| `Le(value=N)` | Less than or equal to N |

**Strings** (`dature.validators.string`):

| Validator | Description |
|-----------|-------------|
| `MinLength(value=N)` | Minimum string length |
| `MaxLength(value=N)` | Maximum string length |
| `RegexPattern(pattern=r"...")` | Match regex pattern |

**Sequences** (`dature.validators.sequence`):

| Validator | Description |
|-----------|-------------|
| `MinItems(value=N)` | Minimum number of items |
| `MaxItems(value=N)` | Maximum number of items |
| `UniqueItems()` | All items must be unique |

Multiple validators can be combined:

```python
port: Annotated[int, Ge(value=1), Le(value=65535)]
tags: Annotated[list[str], MinItems(value=1), MaxItems(value=10), UniqueItems()]
```

## Root Validators

Validate the entire object after loading:

```python
--8<-- "examples/docs/validation_root.py"
```

Root validators receive the fully constructed dataclass instance and return `True` if valid.

## Metadata Validators

Field validators can be specified in `LoadMetadata` using the `validators` parameter. Useful when the same dataclass is loaded from different sources with different validation rules. These validators **complement** (not replace) any `Annotated` validators:

```python
--8<-- "examples/docs/validation_metadata.py"
```

A single validator can be passed directly. Multiple validators require a tuple:

```python
validators={
    F[Config].port: (Gt(value=0), Lt(value=65536)),  # tuple for multiple
    F[Config].host: MinLength(value=1),               # single, no tuple needed
}
```

Nested fields are supported:

```python
validators={
    F[Config].database.host: MinLength(value=1),
    F[Config].database.port: Gt(value=0),
}
```

## Custom Validators

Create your own validators by implementing `get_validator_func()` and `get_error_message()`. The validator must be a frozen dataclass:

```python
--8<-- "examples/docs/validation_custom.py"
```

On validation failure:

```
Config loading errors (1)

  [workers]  Value must be divisible by 32
   └── FILE 'config.yaml', line 1
       workers: 50
```

Custom validators can be combined with built-in ones in `Annotated`.

## `__post_init__` and `@property`

Standard dataclass `__post_init__` and `@property` work as expected — dature preserves them during loading:

```python
--8<-- "examples/docs/validation_post_init.py"
```

Both approaches work in function mode and decorator mode.

## Error Format

Validation errors include source location and context:

```
Config loading errors (1)

  [port]  Value must be >= 1
   └── FILE 'config.json5', line 2
       port: -1
```

All field errors are collected and reported together — dature doesn't stop at the first error.
