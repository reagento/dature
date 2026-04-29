# Supported Types

## Type Coercion

dature infers the target Python type from the dataclass annotation and coerces
the input accordingly. Input sources:

- **YAML** (1.1 / 1.2) — parses most scalars, date/time and collections natively
- **JSON** — strict JSON; non-native values (`Decimal`, `datetime`, `UUID`, …) pass as quoted strings
- **JSON5** — JSON plus single quotes, unquoted keys, hex literals, `Infinity`, `NaN`
- **TOML** (1.0 / 1.1) — parses scalars, date/time and collections natively; requires double-quoted strings
- **INI** — all values are strings; collections are JSON literals
- **ENV / ENV File** — all values are strings; nested fields use `__`
- **Docker Secrets** — each file = one field (filename = field name, uppercased); file content is the value

Across this page the **Syntax** column shows the raw value — apply the source
format's own quoting rules around it.

### Scalars

=== "YAML"

    | Type  | Python            | Syntax               | Notes                                |
    |-------|-------------------|----------------------|--------------------------------------|
    | str   | `"hello world"`   | `hello world`        | quotes optional                      |
    | int   | `42`              | `42`                 | —                                    |
    | float | `3.14`            | `3.14`               | —                                    |
    | float | `float("inf")`    | `.inf`               | —                                    |
    | float | `float("nan")`    | `.nan`               | —                                    |
    | bool  | `True` / `False`  | `true` / `false`     | YAML 1.1 also: `yes`/`no`/`on`/`off` |
    | None  | `None`            | `null` / `~` / empty | —                                    |

=== "JSON"

    | Type  | Python            | Syntax           | Notes                    |
    |-------|-------------------|------------------|--------------------------|
    | str   | `"hello"`         | `"hello"`        | —                        |
    | int   | `42`              | `42`             | —                        |
    | float | `3.14`            | `3.14`           | —                        |
    | float | `float("inf")`    | `"inf"`          | JSON has no native `inf` |
    | float | `float("nan")`    | `"nan"`          | JSON has no native `nan` |
    | bool  | `True` / `False`  | `true` / `false` | —                        |
    | None  | `None`            | `null`           | —                        |

=== "JSON5"

    | Type  | Python            | Syntax                | Notes |
    |-------|-------------------|-----------------------|-------|
    | str   | `"hello"`         | `"hello"` / `'hello'` | —     |
    | int   | `42` / `255`      | `42` / `0xff`         | —     |
    | float | `3.14`            | `3.14`                | —     |
    | float | `float("inf")`    | `Infinity`            | —     |
    | float | `float("nan")`    | `NaN`                 | —     |
    | bool  | `True` / `False`  | `true` / `false`      | —     |
    | None  | `None`            | `null`                | —     |

=== "TOML"

    | Type  | Python            | Syntax                                | Notes                                    |
    |-------|-------------------|---------------------------------------|------------------------------------------|
    | str   | `"hello world"`   | `"hello world"`                       | quotes required                          |
    | int   | `42`              | `42` / `0xff` / `0o7` / `0b101`       | —                                        |
    | float | `3.14`            | `3.14`                                | —                                        |
    | float | `float("inf")`    | `inf`                                 | —                                        |
    | float | `float("nan")`    | `nan`                                 | —                                        |
    | bool  | `True` / `False`  | `true` / `false`                      | —                                        |
    | None  | `None`            | `""`                                  | empty string = None (TOML has no `null`) |

=== "INI"

    | Type  | Python            | Syntax        | Notes                            |
    |-------|-------------------|---------------|----------------------------------|
    | str   | `"hello"`         | `key = hello` | —                                |
    | int   | `42`              | `key = 42`    | —                                |
    | float | `3.14`            | `key = 3.14`  | —                                |
    | float | `float("inf")`    | `key = inf`   | —                                |
    | float | `float("nan")`    | `key = nan`   | —                                |
    | bool  | `True` / `False`  | `key = true`  | also: `false`/`yes`/`no`/`1`/`0` |
    | None  | `None`            | `key =`       | —                                |

=== "ENV / ENV File"

    | Type  | Python            | Syntax               | Notes                            |
    |-------|-------------------|----------------------|----------------------------------|
    | str   | `"hello"`         | `STRING_VALUE=hello` | —                                |
    | int   | `42`              | `INTEGER_VALUE=42`   | —                                |
    | float | `3.14`            | `FLOAT_VALUE=3.14`   | —                                |
    | float | `float("inf")`    | `FLOAT_INF=inf`      | —                                |
    | float | `float("nan")`    | `FLOAT_NAN=nan`      | —                                |
    | bool  | `True` / `False`  | `BOOLEAN_VALUE=true` | also: `false`/`1`/`0`/`yes`/`no` |
    | None  | `None`            | `NONE_VALUE=`        | —                                |

=== "Docker Secrets"

    | Type  | Python            | File → content           | Notes                            |
    |-------|-------------------|--------------------------|----------------------------------|
    | str   | `"hello"`         | `STRING_VALUE` → `hello` | —                                |
    | int   | `42`              | `INTEGER_VALUE` → `42`   | —                                |
    | float | `3.14`            | `FLOAT_VALUE` → `3.14`   | —                                |
    | float | `float("inf")`    | `FLOAT_INF` → `inf`      | —                                |
    | float | `float("nan")`    | `FLOAT_NAN` → `nan`      | —                                |
    | bool  | `True` / `False`  | `BOOLEAN_VALUE` → `true` | also: `false`/`1`/`0`/`yes`/`no` |
    | None  | `None`            | file absent or empty     | —                                |

### Numeric

Always encoded as a string across all sources.

| Type     | Python                                              | Syntax                                |
|----------|-----------------------------------------------------|---------------------------------------|
| Decimal  | `Decimal("3.14159265358979323846264338327950288")`  | `3.14159265358979323846264338327950288` |
| complex  | `complex(1, 2)`                                     | `1+2j`                                |
| Fraction | `Fraction(1, 3)`                                    | `1/3`                                 |

### Date / time

TOML and YAML 1.2 parse date / datetime / time natively; JSON / JSON5 require
quoted strings; INI / ENV / ENV File / Docker Secrets take them as bare strings.

| Type            | Python                                                            | Syntax                        | Notes                           |
|-----------------|-------------------------------------------------------------------|-------------------------------|---------------------------------|
| date            | `date(2024, 1, 15)`                                               | `2024-01-15`                  | —                               |
| datetime        | `datetime(2024, 1, 15, 10, 30)`                                   | `2024-01-15T10:30:00`         | —                               |
| datetime (UTC)  | `datetime(2024, 1, 15, 10, 30, tzinfo=UTC)`                       | `2024-01-15T10:30:00Z`        | —                               |
| datetime (TZ)   | `datetime(2024, 1, 15, 10, 30, tzinfo=ZoneInfo("Europe/Moscow"))` | `2024-01-15T10:30:00+03:00`   | `±HH:MM` offset                 |
| time            | `time(10, 30)`                                                    | `10:30:00`                    | quote in YAML 1.1 (sexagesimal) |
| timedelta       | `timedelta(hours=2, minutes=30)`                                  | `2:30:00`                     | [all formats below](#timedelta) |

#### timedelta

`timedelta` is always a string; the same formats are accepted in every source.

| Format spec                                              | Syntax example            | Python                                                              |
|----------------------------------------------------------|---------------------------|---------------------------------------------------------------------|
| `hh:mm`                                                  | `2:30`                    | `timedelta(hours=2, minutes=30)`                                    |
| `hh:mm:ss`                                               | `2:30:00`                 | `timedelta(hours=2, minutes=30)`                                    |
| `hh:mm:ss.microseconds`                                  | `2:03:04.500000`          | `timedelta(hours=2, minutes=3, seconds=4, microseconds=500000)`     |
| `N day[s][,] hh:mm[:ss[.microseconds]]`                  | `1 day, 2:30:00`          | `timedelta(days=1, hours=2, minutes=30)`                            |
| `N week[s][,] [N day[s][,]] [hh:mm[:ss[.microseconds]]]` | `2 weeks, 3 days 1:02:03` | `timedelta(weeks=2, days=3, hours=1, minutes=2, seconds=3)`         |
| `N day[s]`                                               | `3 days`                  | `timedelta(days=3)`                                                 |
| `N week[s]`                                              | `2 weeks`                 | `timedelta(weeks=2)`                                                |

All time components and days/weeks support negative values: `-2:30`,
`-1 day, 23:59:59`, `-2 weeks`.

### Collections

=== "YAML"

    | Type                 | Python                  | Syntax      | Notes              |
    |----------------------|-------------------------|-------------|--------------------|
    | list[int]            | `[1, 2, 3]`             | see below   | inline or block    |
    | tuple[int, int, int] | `(1, 2, 3)`             | `[1, 2, 3]` | fixed length       |
    | set[int]             | `{1, 2, 3}`             | `[1, 2, 3]` | duplicates removed |
    | frozenset[int]       | `frozenset({1, 2, 3})`  | `[1, 2, 3]` | duplicates removed |
    | dict[str, str]       | `{"k": "v"}`            | see below   | inline or block    |
    | deque[str]           | `deque(["a", "b"])`     | `[a, b]`    | —                  |

    Inline (flow) vs block style for `list` and `dict`:

    ```yaml
    # list
    items_inline: [1, 2, 3]
    items_block:
      - 1
      - 2
      - 3

    # dict
    address_inline: {city: Moscow, zip_code: "101000"}
    address_block:
      city: Moscow
      zip_code: "101000"
    ```

=== "JSON"

    | Type                 | Python                  | Syntax             | Notes               |
    |----------------------|-------------------------|--------------------|---------------------|
    | list[int]            | `[1, 2, 3]`             | `[1, 2, 3]`        | —                   |
    | tuple[int, int, int] | `(1, 2, 3)`             | `[1, 2, 3]`        | fixed length        |
    | set[int]             | `{1, 2, 3}`             | `[1, 2, 3]`        | duplicates removed  |
    | frozenset[int]       | `frozenset({1, 2, 3})`  | `[1, 2, 3]`        | duplicates removed  |
    | dict[str, str]       | `{"k": "v"}`            | `{"k": "v"}`       | int keys as strings |
    | deque[str]           | `deque(["a", "b"])`     | `["a", "b"]`       | —                   |

=== "JSON5"

    | Type                 | Python                  | Syntax             | Notes               |
    |----------------------|-------------------------|--------------------|---------------------|
    | list[int]            | `[1, 2, 3]`             | `[1, 2, 3]`        | —                   |
    | tuple[int, int, int] | `(1, 2, 3)`             | `[1, 2, 3]`        | fixed length        |
    | set[int]             | `{1, 2, 3}`             | `[1, 2, 3]`        | duplicates removed  |
    | frozenset[int]       | `frozenset({1, 2, 3})`  | `[1, 2, 3]`        | duplicates removed  |
    | dict[str, str]       | `{"k": "v"}`            | `{k: "v"}`         | unquoted keys ok    |
    | deque[str]           | `deque(["a", "b"])`     | `["a", "b"]`       | —                   |

=== "TOML"

    | Type                 | Python                  | Syntax         | Notes              |
    |----------------------|-------------------------|----------------|--------------------|
    | list[int]            | `[1, 2, 3]`             | `[1, 2, 3]`    | —                  |
    | tuple[int, int, int] | `(1, 2, 3)`             | `[1, 2, 3]`    | fixed length       |
    | set[int]             | `{1, 2, 3}`             | `[1, 2, 3]`    | duplicates removed |
    | frozenset[int]       | `frozenset({1, 2, 3})`  | `[1, 2, 3]`    | duplicates removed |
    | dict[str, str]       | `{"k": "v"}`            | see below      | table or inline    |
    | deque[str]           | `deque(["a", "b"])`     | `["a", "b"]`   | —                  |

    Dict forms:

    ```toml
    # Inline table
    address = { city = "Moscow", zip_code = "101000" }

    # Multiline inline table (TOML 1.1 only)
    address = {
        city = "Moscow",
        zip_code = "101000",
    }

    # Table section
    [address]
    city = "Moscow"
    zip_code = "101000"

    # Nested tables
    [dict_nested.level1.level2]
    level3 = "deep_value"
    ```

=== "INI"

    | Type                 | Python                  | Syntax                         | Notes        |
    |----------------------|-------------------------|--------------------------------|--------------|
    | list[int]            | `[1, 2, 3]`             | `key = [1, 2, 3]`              | JSON literal |
    | tuple[int, int, int] | `(1, 2, 3)`             | `key = [1, 2, 3]`              | JSON literal |
    | set[int]             | `{1, 2, 3}`             | `key = [1, 2, 3]`              | JSON literal |
    | frozenset[int]       | `frozenset({1, 2, 3})`  | `key = [1, 2, 3]`              | JSON literal |
    | dict[str, str]       | `{"k": "v"}`            | `key = {"k": "v"}`             | JSON literal |
    | deque[str]           | `deque(["a", "b"])`     | `key = ["a", "b"]`             | JSON literal |

=== "ENV / ENV File"

    | Type                 | Python                  | Syntax                                    | Notes                     |
    |----------------------|-------------------------|-------------------------------------------|---------------------------|
    | list[int]            | `[1, 2, 3]`             | `VAR=[1,2,3]`                             | JSON literal              |
    | tuple[int, int, int] | `(1, 2, 3)`             | `VAR=[1,2,3]`                             | JSON literal              |
    | set[int]             | `{1, 2, 3}`             | `VAR=[1,2,3]`                             | JSON literal              |
    | frozenset[int]       | `frozenset({1, 2, 3})`  | `VAR=[1,2,3]`                             | JSON literal              |
    | dict[str, str]       | `{"k": "v"}`            | `VAR__K=v` or `VAR={"k":"v"}`             | `__` separator or JSON    |
    | deque[str]           | `deque(["a", "b"])`     | `VAR=["a","b"]`                           | JSON literal              |

=== "Docker Secrets"

    | Type                 | Python                  | File → content                                    | Notes                     |
    |----------------------|-------------------------|---------------------------------------------------|---------------------------|
    | list[int]            | `[1, 2, 3]`             | `VAR` → `[1,2,3]`                                 | JSON literal              |
    | tuple[int, int, int] | `(1, 2, 3)`             | `VAR` → `[1,2,3]`                                 | JSON literal              |
    | set[int]             | `{1, 2, 3}`             | `VAR` → `[1,2,3]`                                 | JSON literal              |
    | frozenset[int]       | `frozenset({1, 2, 3})`  | `VAR` → `[1,2,3]`                                 | JSON literal              |
    | dict[str, str]       | `{"k": "v"}`            | `VAR__K` → `v` or `VAR` → `{"k":"v"}`             | `__` separator or JSON    |
    | deque[str]           | `deque(["a", "b"])`     | `VAR` → `["a","b"]`                               | JSON literal              |

### Binary & encoding

Always encoded as a string.

| Type           | Python                    | Syntax             | Notes                             |
|----------------|---------------------------|--------------------|-----------------------------------|
| bytes          | `b"binary data"`          | `binary data`      | UTF-8 encoded                     |
| bytearray      | `bytearray(b"binary")`    | `binary`           | UTF-8 encoded                     |
| Base64UrlBytes | `b"Hello World"`          | `SGVsbG8gV29ybGQ=` | base64url-decoded to bytes        |
| Base64UrlStr   | `"secret token"`          | `c2VjcmV0IHRva2Vu` | base64url-decoded to UTF-8 string |

### Custom fields

Always encoded as a string.

| Type              | Python                                      | Syntax               | Notes                |
|-------------------|---------------------------------------------|----------------------|----------------------|
| SecretStr         | `SecretStr("supersecret123")`               | `supersecret123`     | masked on repr       |
| PaymentCardNumber | `PaymentCardNumber("4111111111111111")`     | `4111111111111111`   | Luhn-validated       |
| ByteSize          | `ByteSize("1.5 GB")`                        | `1.5 GB`             | parses unit suffixes |

### Paths

Always encoded as a string.

| Type            | Python                                       | Syntax                |
|-----------------|----------------------------------------------|-----------------------|
| Path            | `Path("/usr/local/bin")`                     | `/usr/local/bin`      |
| PurePosixPath   | `PurePosixPath("/etc/hosts")`                | `/etc/hosts`          |
| PureWindowsPath | `PureWindowsPath("C:/Windows/System32")`     | `C:/Windows/System32` |

### Network

Always encoded as a string.

| Type          | Python                               | Syntax              |
|---------------|--------------------------------------|---------------------|
| IPv4Address   | `IPv4Address("192.168.1.1")`         | `192.168.1.1`       |
| IPv6Address   | `IPv6Address("2001:db8::1")`         | `2001:db8::1`       |
| IPv4Network   | `IPv4Network("192.168.1.0/24")`      | `192.168.1.0/24`    |
| IPv6Network   | `IPv6Network("2001:db8::/32")`       | `2001:db8::/32`     |
| IPv4Interface | `IPv4Interface("192.168.1.1/24")`    | `192.168.1.1/24`    |
| IPv6Interface | `IPv6Interface("2001:db8::1/32")`    | `2001:db8::1/32`    |

### Identifiers

Always encoded as a string.

| Type | Python                                              | Syntax                                     |
|------|-----------------------------------------------------|--------------------------------------------|
| UUID | `UUID("550e8400-e29b-41d4-a716-446655440000")`      | `550e8400-e29b-41d4-a716-446655440000`     |
| URL  | `urlparse("https://example.com/path?q=v#frag")`     | `https://example.com/path?q=v#frag`        |

### Enum / Flag / Literal

| Type    | Python                                  | Syntax  | Notes                              |
|---------|-----------------------------------------|---------|------------------------------------|
| Enum    | `Color.GREEN`                           | `green` | matched by value, not member name  |
| Flag    | `Permission.READ \| Permission.WRITE`   | `3`     | integer of combined bits           |
| Literal | `"info"`                                | `info`  | one of the declared values         |

### Nested dataclasses

```python
--8<-- "examples/docs/supported_types/nested_dc.py:schema"
```

=== "YAML"

    ```yaml
    --8<-- "examples/docs/supported_types/sources/nested_dc.yaml"
    ```

=== "JSON"

    ```json
    --8<-- "examples/docs/supported_types/sources/nested_dc.json"
    ```

=== "JSON5"

    ```json5
    --8<-- "examples/docs/supported_types/sources/nested_dc.json5"
    ```

=== "TOML"

    ```toml
    --8<-- "examples/docs/supported_types/sources/nested_dc.toml"
    ```

=== "INI"

    ```ini
    --8<-- "examples/docs/supported_types/sources/nested_dc.ini"
    ```

=== "ENV / ENV File"

    ```bash
    --8<-- "examples/docs/supported_types/sources/nested_dc.env"
    ```

=== "Docker Secrets"

    Directory `nested_dc_docker_secrets/` — one file per (uppercased,
    `__`-joined) field path; file content is the value.

    | File                      | Content                                                       |
    |---------------------------|---------------------------------------------------------------|
    | `ADDRESS__CITY`           | `Moscow`                                                      |
    | `ADDRESS__ZIP_CODE`       | `101000`                                                      |
    | `TAGS`                    | `[{"name":"urgent","priority":1},{"name":"low","priority":5}]`|
    | `ADDRS__HOME__CITY`       | `Berlin`                                                      |
    | `ADDRS__HOME__ZIP_CODE`   | `10115`                                                       |
    | `ADDRS__WORK__CITY`       | `Paris`                                                       |
    | `ADDRS__WORK__ZIP_CODE`   | `75001`                                                       |

### Other stdlib

| Type       | Python                     | Syntax       |
|------------|----------------------------|--------------|
| re.Pattern | `re.compile(r"^[a-z]+$")`  | `^[a-z]+$`   |

For custom types and file format loaders, see [Custom Types & Loaders](advanced/custom_types.md).
