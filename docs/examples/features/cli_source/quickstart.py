"""Quickstart: load CLI args into a dataclass."""

import argparse
from dataclasses import dataclass

import dature


@dataclass
class Config:
    name: str = "demo"
    port: int = 8080
    debug: bool = False


parser = argparse.ArgumentParser()
parser.add_argument("--name")
parser.add_argument("--port", type=int)
parser.add_argument("--debug", action="store_true")


def main() -> None:
    config = dature.load(dature.ArgparseSource(parser=parser), schema=Config)
    print(config)


if __name__ == "__main__":
    main()
