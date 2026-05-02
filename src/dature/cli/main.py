import argparse
import sys
from typing import cast

from dature.cli.inspect_cmd import cmd_inspect
from dature.cli.parsing import CliArgs, add_common_args, derive_cli_schema
from dature.cli.validate_cmd import cmd_validate
from dature.main import load
from dature.sources.argparse_ import ArgparseSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dature",
        description="dature CLI: inspect and validate dataclass-based configuration.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser(
        "inspect",
        help="Print the load report (sources, field origins, merged data).",
    )
    add_common_args(inspect)
    inspect.add_argument(
        "--field",
        default=None,
        metavar="DOTTED.PATH",
        help="Filter origins and merged data by a dotted field path.",
    )
    inspect.add_argument(
        "--format",
        choices=["json", "text"],
        default=None,
        help="Output format (default: json).",
    )

    validate = subparsers.add_parser(
        "validate",
        help="Try loading the schema; exit 0 on success, 1 on validation failure, 2 on usage error.",
    )
    add_common_args(validate)

    return parser


def main() -> int:
    parser = build_parser()
    schema = derive_cli_schema()
    cli_args = cast("CliArgs", load(ArgparseSource(parser=parser), schema=schema))

    if cli_args.inspect is not None:
        return cmd_inspect(cli_args.inspect)
    if cli_args.validate is not None:
        return cmd_validate(cli_args.validate)
    msg = f"unreachable: unknown command {cli_args.command!r}"
    raise RuntimeError(msg)


if __name__ == "__main__":
    sys.exit(main())
