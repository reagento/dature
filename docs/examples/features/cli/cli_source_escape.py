"""Escaping commas inside ``--source`` values (``\\,``)."""

from dature import EnvSource
from dature.cli.parsing import parse_source_spec

klass, kwargs = parse_source_spec(r"type=dature.EnvSource,prefix=APP\,X_")

assert klass is EnvSource
assert kwargs == {"prefix": "APP,X_"}
