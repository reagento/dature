# --8<-- [start:setup]
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
# --8<-- [end:setup]

# --8<-- [start:example]
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev")
    parser.add_argument("--port", type=int)

    ns = parser.parse_args()  # 1. reading env
    env = ns.env

    config = dature.load(
        dature.JsonSource(file=SOURCES_DIR / f"config.{env}.json"),  # 2. using env
        dature.ArgparseSource(parser=parser),  # 3. parsing env again
        schema=AppConfig,
    )
    print(config)


if __name__ == "__main__":
    main()
# --8<-- [end:example]
