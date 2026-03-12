"""Field groups — error on partial override (basic)."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from dature import F, FieldGroup, LoadMetadata, MergeMetadata, load
from dature.errors.exceptions import FieldGroupError

SOURCES_DIR = Path(__file__).parent / "sources"
SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    user: str
    password: str


try:
    load(
        MergeMetadata(
            sources=(
                LoadMetadata(file_=SHARED_DIR / "common_field_groups_defaults.yaml"),
                LoadMetadata(file_=SOURCES_DIR / "field_groups_partial_overrides.yaml"),
            ),
            field_groups=(
                FieldGroup(F[Config].host, F[Config].port),
                FieldGroup(F[Config].user, F[Config].password),
            ),
        ),
        Config,
    )
except FieldGroupError as exc:
    defaults_path = str(SHARED_DIR / "common_field_groups_defaults.yaml")
    overrides_path = str(SOURCES_DIR / "field_groups_partial_overrides.yaml")
    assert str(exc) == dedent(f"""\
        Config field group errors (1)

          Field group (host, port) partially overridden in source 1
            changed:   host (from source yaml1.2 '{overrides_path}')
            unchanged: port (from source yaml1.2 '{defaults_path}')
""")
