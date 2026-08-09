import json
from dataclasses import asdict
from typing import Any

from dature.report import LoadReport
from dature.report_types import FieldOrigin
from dature.type_aliases import JSONValue


def _filter_origins(report: LoadReport, field: str | None) -> tuple[FieldOrigin, ...]:
    if field is None:
        return report.field_origins
    prefix = field + "."
    return tuple(o for o in report.field_origins if o.key == field or o.key.startswith(prefix))


def _filter_merged(merged: Any, field: str | None) -> Any:  # noqa: ANN401
    if field is None:
        return merged
    cur = merged
    for part in field.split("."):
        if not isinstance(cur, dict) or part not in cur:
            msg = f"Field {field!r} not found in merged data"
            raise KeyError(msg)
        cur = cur[part]
    return cur


def _strategy_name(report: LoadReport) -> str | None:
    if report.strategy is None:
        return None
    return type(report.strategy).__name__


def format_json(report: LoadReport, *, field: str | None = None) -> str:
    payload = {
        "schema": report.dataclass_name,
        "strategy": _strategy_name(report),
        "sources": [asdict(s) for s in report.sources],
        "field_origins": [asdict(o) for o in _filter_origins(report, field)],
        "merged_data": _filter_merged(report.merged_data, field),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def format_text(report: LoadReport, *, field: str | None = None) -> str:
    lines: list[str] = []
    strategy = _strategy_name(report) or "—"
    lines.append(f"Schema: {report.dataclass_name} (strategy: {strategy})")
    lines.append("")

    lines.append("Sources:")
    for s in report.sources:
        location = s.file_path or "—"
        lines.append(f"  [{s.index}] {s.loader_type:<12} {location}")
    lines.append("")

    origins = _filter_origins(report, field)
    if origins:
        lines.append("Field origins:")
        max_key = max(len(o.key) for o in origins)
        for o in origins:
            value_repr = json.dumps(o.value, ensure_ascii=False, default=str)
            origin_label = o.source_file or o.source_loader_type
            lines.append(
                f"  {o.key:<{max_key}} = {value_repr}   <- [{o.source_index}] {origin_label}",
            )
        lines.append("")

    lines.append("Merged data:")
    merged = _filter_merged(report.merged_data, field)
    if isinstance(merged, dict):
        merged_text = json.dumps(merged, indent=2, ensure_ascii=False, default=str)
        lines.extend("  " + line for line in merged_text.splitlines())
    else:
        lines.append("  " + json.dumps(merged, ensure_ascii=False, default=str))

    return "\n".join(lines)


def _table_border(widths: tuple[int, ...]) -> str:
    return "+" + "+".join("-" * (width + 2) for width in widths) + "+"


def _table_row(values: tuple[str, ...], widths: tuple[int, ...]) -> str:
    return "|" + "|".join(f" {value:<{width}} " for value, width in zip(values, widths, strict=True)) + "|"


def _table_source_label(origin: FieldOrigin) -> str:
    if origin.source_file is not None:
        return origin.source_file
    return origin.source_loader_type


def _table_value_repr(value: JSONValue) -> str:
    if isinstance(value, str):
        return repr(value)
    return json.dumps(value, ensure_ascii=False, default=str)


def _flatten_table_values(key: str, value: JSONValue) -> tuple[tuple[str, JSONValue], ...]:
    if not isinstance(value, dict) or not value:
        return ((key, value),)

    rows: list[tuple[str, JSONValue]] = []
    for child_key, child_value in value.items():
        rows.extend(_flatten_table_values(f"{key}.{child_key}", child_value))
    return tuple(rows)


def format_table(report: LoadReport, *, field: str | None = None) -> str:
    _filter_merged(report.merged_data, field)

    headers = ("key", "source", "value")
    rows: list[tuple[str, str, str]] = []

    for origin in _filter_origins(report, field):
        source = _table_source_label(origin)
        rows.extend(
            (key, source, _table_value_repr(value)) for key, value in _flatten_table_values(origin.key, origin.value)
        )

    widths = tuple(max([len(headers[i]), *(len(row[i]) for row in rows)]) for i in range(3))

    border = _table_border(widths)
    lines = [
        border,
        _table_row(headers, widths),
        border,
    ]
    lines.extend(_table_row(row, widths) for row in rows)
    lines.append(border)

    return "\n".join(lines)
