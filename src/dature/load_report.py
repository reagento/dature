import logging
import warnings
from dataclasses import dataclass
from typing import Any

from dature.metadata import MergeStrategy
from dature.types import JSONValue

logger = logging.getLogger("dature")

_REPORT_ATTR = "__dature_load_report__"


# --8<-- [start:report-structure]
@dataclass(frozen=True, slots=True, kw_only=True)
class SourceEntry:
    index: int
    file_path: str | None
    loader_type: str
    raw_data: JSONValue


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldOrigin:
    key: str
    value: JSONValue
    source_index: int
    source_file: str | None
    source_loader_type: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LoadReport:
    dataclass_name: str
    strategy: MergeStrategy | None
    sources: tuple[SourceEntry, ...]
    field_origins: tuple[FieldOrigin, ...]
    merged_data: JSONValue


# --8<-- [end:report-structure]
def compute_field_origins(
    *,
    raw_dicts: list[JSONValue],
    source_entries: tuple[SourceEntry, ...],
    strategy: MergeStrategy,
) -> tuple[FieldOrigin, ...]:
    first_source: dict[str, int] = {}
    last_source: dict[str, int] = {}
    last_value: dict[str, JSONValue] = {}

    for i, raw in enumerate(raw_dicts):
        if not isinstance(raw, dict):
            continue
        for key, value in _flatten_dict(raw, prefix=""):
            if key not in first_source:
                first_source[key] = i
            last_source[key] = i
            last_value[key] = value

    origins: list[FieldOrigin] = []
    for key in sorted(last_source):
        if strategy == MergeStrategy.FIRST_WINS:
            winner_idx = first_source[key]
        else:
            winner_idx = last_source[key]

        winner = source_entries[winner_idx]
        origins.append(
            FieldOrigin(
                key=key,
                value=last_value[key],
                source_index=winner_idx,
                source_file=winner.file_path,
                source_loader_type=winner.loader_type,
            ),
        )

    return tuple(origins)


def _flatten_dict(
    data: JSONValue,
    *,
    prefix: str,
) -> list[tuple[str, JSONValue]]:
    """Flatten nested dicts into dot-separated key-value pairs (leaf nodes only)."""
    if not isinstance(data, dict):
        return []

    result: list[tuple[str, JSONValue]] = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(_flatten_dict(value, prefix=full_key))
        else:
            result.append((full_key, value))
    return result


# --8<-- [start:get-load-report]
def get_load_report(instance: Any) -> LoadReport | None:  # noqa: ANN401
    report = getattr(instance, _REPORT_ATTR, None)
    if isinstance(report, LoadReport):
        return report
    warnings.warn(
        "To get LoadReport, pass debug=True to load()",
        stacklevel=2,
    )
    return None


# --8<-- [end:get-load-report]


def attach_load_report(target: Any, report: LoadReport) -> None:  # noqa: ANN401
    setattr(target, _REPORT_ATTR, report)
