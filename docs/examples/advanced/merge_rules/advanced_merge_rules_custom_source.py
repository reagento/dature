"""Custom source strategy — files merge `last_wins`, env overrides on top."""

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
    """Shallow overlay: top-level keys of b replace those of a."""
    return {**a, **b} if isinstance(a, dict) and isinstance(b, dict) else b


class EnvOverrides:
    """Files merge `last_wins`; env sources overlay shallowly on top."""

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


# Type-check that the class satisfies the public Protocol.
strategy: SourceMergeStrategy = EnvOverrides()

config = dature.load(
    dature.Yaml12Source(file=SHARED_DIR / "common_defaults.yaml"),
    dature.Yaml12Source(file=SHARED_DIR / "common_overrides.yaml"),
    schema=Config,
    strategy=strategy,
)

# `last_wins` between two file sources — the override file wins.
assert config.host == "production.example.com"
assert config.port == 8080
