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
        file_=str(SOURCES_DIR / "nested.yaml"),
        field_mapping={
            F[User].name: "fullName",
            F[User].address: "location",
            F[Address].city: "cityName",
            F[Address].street: "streetName",
        },
    ),
    User,
)

print(f"name: {config.name}")  # Alice
print(f"address.city: {config.address.city}")  # Paris
print(f"address.street: {config.address.street}")  # Rue de Rivoli
