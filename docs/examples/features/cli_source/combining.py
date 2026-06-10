# --8<-- [start:setup]
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
# --8<-- [end:setup]

# --8<-- [start:example]
def main() -> None:
    config = dature.load(
        dature.JsonSource(file=SOURCES_DIR / "config.json"),
        dature.EnvSource(prefix="MYAPP_"),
        dature.ArgparseSource(parser=parser),
        schema=Config,
    )
    print(config)


if __name__ == "__main__":
    main()
# --8<-- [end:example]
