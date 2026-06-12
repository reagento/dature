from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]
import argparse
from dataclasses import dataclass

import dature


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
        dature.JsonSource(file=SOURCES_DIR / "config.json"),
        dature.EnvSource(prefix="MYAPP_"),
        dature.ArgparseSource(parser=parser),
        schema=Config,
    )
    print(config)


if __name__ == "__main__":
    main()
# --8<-- [end:example]