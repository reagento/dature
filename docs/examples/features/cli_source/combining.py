"""Combining ArgparseSource with file and env sources via load()."""

import argparse
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080
    debug: bool = False


parser = argparse.ArgumentParser()
parser.add_argument("--host")
parser.add_argument("--port", type=int)


def main() -> None:
    config = dature.load(
        dature.JsonSource(file=SOURCES_DIR / "config.json"),  # baseline
        dature.EnvSource(prefix="MYAPP_"),  # per-deployment overrides
        dature.ArgparseSource(parser=parser),  # operator overrides (wins last)
        schema=Config,
    )
    print(config)


if __name__ == "__main__":
    main()
