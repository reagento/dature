# Special Types

## SecretStr

See [Masking — Examples](../features/masking.md#examples).

## ByteSize

Parses human-readable sizes:

```python
from dature.fields.byte_size import ByteSize

@dataclass
class Config:
    max_upload: ByteSize

# config.yaml: { max_upload: "1.5 GB" }
```

Supported units: B, KB, MB, GB, TB, PB, KiB, MiB, GiB, TiB, PiB.

## PaymentCardNumber

Validates using the Luhn algorithm and detects the brand:

```python
from dature.fields.payment_card import PaymentCardNumber

@dataclass
class Config:
    card: PaymentCardNumber

config = load(meta, Config)
print(config.card.brand)   # Visa
print(config.card.masked)  # ************1111
```

## URL

Parsed into `urllib.parse.ParseResult`:

```python
from dature.types import URL

@dataclass
class Config:
    api_url: URL

config = load(meta, Config)
print(config.api_url.scheme)  # https
print(config.api_url.netloc)  # api.example.com
```

## Base64UrlBytes / Base64UrlStr

Decoded from Base64 string in the config:

```python
from dature.types import Base64UrlBytes, Base64UrlStr

@dataclass
class Config:
    token: Base64UrlStr      # decoded to str
    data: Base64UrlBytes     # decoded to bytes
```

Full example:

=== "Python"

    ```python
    --8<-- "examples/docs/advanced_special_types.py"
    ```

=== "special_types.yaml"

    ```yaml
    --8<-- "examples/docs/sources/special_types.yaml"
    ```
