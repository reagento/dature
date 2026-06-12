from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
from dataclasses import dataclass

import dature


@dataclass
class Address:
    city: str
    street: str


@dataclass
class User:
    name: str
    address: Address

config = dature.load(
    dature.Yaml12Source(
        file=SOURCES_DIR / "naming_nested_fields.yaml",
        field_mapping={
            dature.F[User].name: "fullName",
            dature.F[User].address: "location",
            dature.F[Address].city: "cityName",
            dature.F[Address].street: "streetName",
        },
    ),
    schema=User,
)

assert config.name == "Alice"
assert config.address.city == "Paris"
assert config.address.street == "Rue de Rivoli"
# --8<-- [end:example]
