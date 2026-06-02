"""Subparsers — discriminator + per-subcommand args via Optional fields."""

import argparse
from dataclasses import dataclass

import dature


@dataclass
class CreateArgs:
    name: str = "default"


@dataclass
class DeleteArgs:
    item_id: int = 0


@dataclass
class Config:
    command: str | None = None
    verbose: bool = False
    create: CreateArgs | None = None
    delete: DeleteArgs | None = None


parser = argparse.ArgumentParser()
parser.add_argument("--verbose", action="store_true")
subs = parser.add_subparsers(dest="command")

create = subs.add_parser("create")
create.add_argument("--name")

delete = subs.add_parser("delete")
delete.add_argument("--item-id", type=int)


def main() -> None:
    config = dature.load(dature.ArgparseSource(parser=parser), schema=Config)
    print(config)


if __name__ == "__main__":
    main()
