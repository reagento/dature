"""Field groups — error on partial override with nested dataclass expansion."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from dature import F, FieldGroup, Merge, Source, load
from dature.errors.exceptions import FieldGroupError

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Database:
    host: str
    port: int


@dataclass
class Config:
    host: str
    port: int
    database: Database


# FieldGroup(F[Config].database, F[Config].port)
# expands to (database.host, database.port, port)
try:
    load(
        Merge(
            Source(file=SOURCES_DIR / "field_groups_nested_defaults.yaml"),
            Source(file=SOURCES_DIR / "advanced_field_groups_expansion_error_overrides.yaml"),
            field_groups=(FieldGroup(F[Config].database, F[Config].port),),
        ),
        Config,
    )
except FieldGroupError as exc:
    defaults_path = str(SOURCES_DIR / "field_groups_nested_defaults.yaml")
    overrides_path = str(SOURCES_DIR / "advanced_field_groups_expansion_error_overrides.yaml")
    assert str(exc) == dedent(f"""\
        Config field group errors (1)

          Field group (database.host, database.port, port) partially overridden in source 1
            changed:   database.host (from source yaml1.2 '{overrides_path}'), port (from source yaml1.2 '{overrides_path}')
            unchanged: database.port (from source yaml1.2 '{defaults_path}')
""")
