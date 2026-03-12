# Special Types

## SecretStr

Wraps a string value so it is never exposed in `str()`, `repr()`, or logs:

```python
--8<-- "examples/docs/advanced/special_types/advanced_special_secret_str.py"
```

Works with `mask_secrets=True` — fields of type `SecretStr` are always detected regardless of field name.

## ByteSize

Parses human-readable sizes into bytes. Supports comparison operators.

```python
--8<-- "examples/docs/advanced/special_types/advanced_special_byte_size.py"
```

Supported units: B, KB, MB, GB, TB, PB, KiB, MiB, GiB, TiB, PiB.

## PaymentCardNumber

Validates using the Luhn algorithm and detects the brand:

```python
--8<-- "examples/docs/advanced/special_types/advanced_special_payment_card.py"
```

## URL

Type alias for `urllib.parse.ParseResult`:

```python
--8<-- "examples/docs/advanced/special_types/advanced_special_url.py"
```

## Base64UrlBytes / Base64UrlStr

Type aliases decoded from Base64 string in the config. `Base64UrlStr` decodes to `str`, `Base64UrlBytes` decodes to `bytes`:

```python
--8<-- "examples/docs/advanced/special_types/advanced_special_base64.py"
```
