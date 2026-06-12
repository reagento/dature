from pathlib import Path
SHARED_DIR = Path(__file__).parents[2] / "shared"

# --8<-- [start:example]
from dataclasses import dataclass
from typing import cast

import dature
from dature.strategies.field import FieldMergeStrategy
from dature.type_aliases import JSONValue


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


class SortedUnion:
    def __call__(self, values: list[JSONValue]) -> JSONValue:
        merged: set[str] = set()
        for chunk in values:
            if isinstance(chunk, list):
                merged.update(str(v) for v in chunk)
        return cast("JSONValue", sorted(merged))


strategy: FieldMergeStrategy = SortedUnion()

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
    field_merges={dature.F[Config].tags: strategy},
)

assert config.tags == ["api", "default", "web"]
# --8<-- [end:example]
