"""field_mapping — nested dataclass renaming with F objects."""

from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Address:
    city: str
    street: str


@dataclass
class User:
    name: str
    address: Address


config = dature.load(
    dature.Source(
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
