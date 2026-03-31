"""Multiple field groups — error when both groups partially overridden."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import dature
from dature.errors import FieldGroupError

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
    dature.load(
        dature.Source(file=SHARED_DIR / "common_field_groups_defaults.yaml"),
        dature.Source(file=SOURCES_DIR / "advanced_field_groups_multiple_error_overrides.yaml"),
        dataclass_=Config,
        field_groups=(
            (dature.F[Config].host, dature.F[Config].port),
            (dature.F[Config].user, dature.F[Config].password),
        ),
    )
except FieldGroupError as exc:
    defaults_path = str(SHARED_DIR / "common_field_groups_defaults.yaml")
    overrides_path = str(SOURCES_DIR / "advanced_field_groups_multiple_error_overrides.yaml")
    assert str(exc) == dedent(f"""\
        Config field group errors (2)

          Field group (host, port) partially overridden in source 1
            changed:   host (from source yaml1.2 '{overrides_path}')
            unchanged: port (from source yaml1.2 '{defaults_path}')

          Field group (user, password) partially overridden in source 1
            changed:   user (from source yaml1.2 '{overrides_path}')
            unchanged: password (from source yaml1.2 '{defaults_path}')
""")
