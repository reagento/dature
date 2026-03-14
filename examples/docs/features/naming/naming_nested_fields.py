"""field_mapping — nested dataclass renaming with F objects."""

from dataclasses import dataclass
from pathlib import Path

from dature import F, LoadMetadata, load

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Address:
    city: str
    street: str


@dataclass
class User:
    name: str
    address: Address


config = load(
    LoadMetadata(
        file_=SOURCES_DIR / "naming_nested_fields.yaml",
        field_mapping={
            F[User].name: "fullName",
            F[User].address: "location",
            F[Address].city: "cityName",
            F[Address].street: "streetName",
        },
    ),
    User,
)

assert config.name == "Alice"
assert config.address.city == "Paris"
assert config.address.street == "Rue de Rivoli"
