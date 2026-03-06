"""Field groups — error on partial override."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from dature import F, FieldGroup, LoadMetadata, MergeMetadata, load
from dature.errors.exceptions import FieldGroupError

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str
    port: int
    debug: bool


try:
    load(
        MergeMetadata(
            sources=(
                LoadMetadata(file_=str(SOURCES_DIR / "field_groups_defaults.yaml")),
                LoadMetadata(file_=str(SOURCES_DIR / "field_groups_partial_overrides.yaml")),
            ),
            field_groups=(FieldGroup(F[Config].host, F[Config].port),),
        ),
        Config,
    )
except FieldGroupError as exc:
    defaults_path = str(SOURCES_DIR / "field_groups_defaults.yaml")
    overrides_path = str(SOURCES_DIR / "field_groups_partial_overrides.yaml")
    assert str(exc) == dedent(f"""\
        Config field group errors (1)

          Field group (host, port) partially overridden in source 1
            changed:   host (from source yaml1.2 '{overrides_path}')
            unchanged: port (from source yaml1.2 '{defaults_path}')
""")
