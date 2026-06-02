"""Nesting via double underscore in dest names."""

import argparse
from dataclasses import dataclass, field

import dature


@dataclass
class Db:
    host: str = "localhost"
    port: int = 5432


@dataclass
class Config:
    db: Db = field(default_factory=Db)


parser = argparse.ArgumentParser()
parser.add_argument("--db--host")
parser.add_argument("--db--port", type=int)


def main() -> None:
    config = dature.load(dature.ArgparseSource(parser=parser), schema=Config)
    print(config)


if __name__ == "__main__":
    main()
