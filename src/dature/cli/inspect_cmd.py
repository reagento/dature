import sys

from dature import load, load_report
from dature.cli.format import format_json, format_table, format_text
from dature.cli.parsing import (
    CliInspectArgs,
    build_load_kwargs_from_dataclass,
    build_sources,
    import_attr,
)
from dature.errors import DatureError, DatureErrorGroup
from dature.errors.rendering import format_dature_error


def cmd_inspect(args: CliInspectArgs) -> int:
    try:
        schema = import_attr(args.schema)
        sources = build_sources(args.source)
        load_kwargs = build_load_kwargs_from_dataclass(args)
    except (ValueError, TypeError, ImportError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        result = load(*sources, schema=schema, debug=True, **load_kwargs)
    except (DatureError, DatureErrorGroup) as exc:
        print(format_dature_error(exc), file=sys.stderr)
        return 1
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    report = load_report(result)
    if report is None:
        print("error: failed to obtain load report", file=sys.stderr)
        return 1

    match args.format:
        case "json":
            formatter = format_json
        case "text":
            formatter = format_text
        case "table":
            formatter = format_table
        case _ as unknown:
            msg = f"Unknown output format: {unknown!r}"
            raise ValueError(msg)

    try:
        output = formatter(report, field=args.field)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0
