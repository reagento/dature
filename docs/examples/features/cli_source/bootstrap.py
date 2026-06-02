"""Bootstrap pattern — peek argv before load() to choose other sources.

argparse parsers are stateless across parse_args() calls, so the user can
parse argv themselves to read a flag (here: --env), then hand the same parser
to ArgparseSource, which parses argv again inside load().
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

import dature

SOURCES_DIR = Path(__file__).parent / "sources"


@dataclass
class AppConfig:
    env: str = "dev"
    host: str = "localhost"
    port: int = 8080


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev")
    parser.add_argument("--port", type=int)

    ns = parser.parse_args()
    env = ns.env

    config = dature.load(
        dature.JsonSource(file=SOURCES_DIR / f"config.{env}.json"),
        dature.ArgparseSource(parser=parser),
        schema=AppConfig,
    )
    print(config)


if __name__ == "__main__":
    main()
