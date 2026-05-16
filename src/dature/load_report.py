import logging
import warnings
from typing import Any

from dature.masking.masking import mask_field_origins, mask_json_value, mask_source_entries
from dature.report_types import FieldOrigin, LoadReport, SourceEntry
from dature.strategies.source import SourceMergeStrategy
from dature.types import JSONValue

__all__ = [
    "FieldOrigin",
    "LoadReport",
    "SourceEntry",
    "attach_load_report",
    "get_load_report",
]

logger = logging.getLogger("dature")

_REPORT_ATTR = "__dature_load_report__"


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


def _build_single_source_report(
    *,
    dataclass_name: str,
    loader_type: str,
    file_path: str | None,
    raw_data: JSONValue,
    secret_paths: frozenset[str] = frozenset(),
) -> LoadReport:
    if secret_paths:
        raw_data = mask_json_value(raw_data, secret_paths=secret_paths)

    source = SourceEntry(
        index=0,
        file_path=file_path,
        loader_type=loader_type,
        raw_data=raw_data,
    )

    origins: list[FieldOrigin] = []
    if isinstance(raw_data, dict):
        for key, value in sorted(raw_data.items()):
            origins.append(
                FieldOrigin(
                    key=key,
                    value=value,
                    source_index=0,
                    source_file=file_path,
                    source_loader_type=loader_type,
                ),
            )

    return LoadReport(
        dataclass_name=dataclass_name,
        strategy=None,
        sources=(source,),
        field_origins=tuple(origins),
        merged_data=raw_data,
    )


def _build_merge_report(
    *,
    dataclass_name: str,
    strategy: SourceMergeStrategy,
    source_entries: tuple[SourceEntry, ...],
    field_origins: tuple[FieldOrigin, ...],
    merged_data: JSONValue,
    secret_paths: frozenset[str] = frozenset(),
) -> LoadReport:
    if secret_paths:
        source_entries = mask_source_entries(source_entries, secret_paths=secret_paths)
        field_origins = mask_field_origins(field_origins, secret_paths=secret_paths)
        merged_data = mask_json_value(merged_data, secret_paths=secret_paths)

    return LoadReport(
        dataclass_name=dataclass_name,
        strategy=strategy,
        sources=source_entries,
        field_origins=field_origins,
        merged_data=merged_data,
    )
