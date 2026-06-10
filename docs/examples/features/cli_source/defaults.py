# --8<-- [start:setup]
import argparse

import dature


parser = argparse.ArgumentParser()

# --env not passed -> key absent
parser.add_argument("--env", default="dev")

# --port not passed -> key absent
parser.add_argument("--port", type=int)

# --debug not passed -> key present, value False
parser.add_argument("--debug", action="store_true")

# --8<-- [end:setup]

# --8<-- [start:example]
def main() -> None:
    src = dature.ArgparseSource(parser=parser)
    print(src.load_raw().data)


if __name__ == "__main__":
    main()
# --8<-- [end:example]
