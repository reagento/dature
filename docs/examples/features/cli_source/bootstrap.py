from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
import argparse
from dataclasses import dataclass

import dature


@dataclass
class AppConfig:
    env: str = "dev"
    host: str = "localhost"
    port: int = 8080

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev")
    parser.add_argument("--port", type=int)

    ns = parser.parse_args()  # 1. parsing argv manually
    env = ns.env

    config = dature.load(
        dature.JsonSource(file=SOURCES_DIR / f"config.{env}.json"),
        dature.ArgparseSource(parser=parser),  # 2. parsing argv again
        schema=AppConfig,
    )
    print(config)


if __name__ == "__main__":
    main()
# --8<-- [end:example]
