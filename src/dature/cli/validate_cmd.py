import sys

from dature import load
from dature.cli.format import format_dature_error
from dature.cli.parsing import (
    CliCommonArgs,
    build_load_kwargs_from_dataclass,
    build_sources,
    import_attr,
)
from dature.errors import DatureConfigError, DatureError


def cmd_validate(args: CliCommonArgs) -> int:
    try:
        schema = import_attr(args.schema)
        sources = build_sources(args.source)
        load_kwargs = build_load_kwargs_from_dataclass(args)
    except (ValueError, TypeError, ImportError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        load(*sources, schema=schema, **load_kwargs)
    except (DatureError, DatureConfigError) as exc:
        print(format_dature_error(exc), file=sys.stderr)
        return 1
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("OK")
    return 0
