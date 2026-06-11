from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import dature
from dature.strategies import LoadCtx, SourceMergeStrategy
from dature.type_aliases import JSONValue

SHARED_DIR = Path(__file__).parents[2] / "shared"


@dataclass
class Config:
    host: str
    port: int
    tags: list[str]


def _dict_overlay(a: JSONValue, b: JSONValue) -> JSONValue:
    return {**a, **b} if isinstance(a, dict) and isinstance(b, dict) else b


class EnvOverrides:
    def __call__(
        self,
        sources: Sequence[dature.Source],
        ctx: LoadCtx,
    ) -> JSONValue:
        base: JSONValue = {}
        for idx, s in enumerate(sources):
            if isinstance(s, dature.EnvSource):
                base = ctx.merge(source_idx=idx, base=base, op=_dict_overlay)
            else:
                base = ctx.merge(source_idx=idx, base=base)
        return base


strategy: SourceMergeStrategy = EnvOverrides()

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
    strategy=strategy,
)

assert config.host == "production.example.com"
assert config.port == 8080

