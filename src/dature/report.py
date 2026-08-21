"""Public load report: aggregate description of a completed dature load.

Owns ``LoadReport`` — the frozen aggregate that callers receive via
:func:`load_report`. Holds tuples of leaf types (``SourceEntry``,
``FieldOrigin``) from :mod:`dature.report_types`, applies secret masking, and
attaches the report to the loaded instance. Not the same as
``_LoadCtxSnapshot`` in :mod:`dature.loading.merge_runtime`, which is an
internal accumulator bridge and not exposed to callers.
"""

import logging
import warnings
from dataclasses import dataclass
from typing import Any

from dature.config import MaskingConfig
from dature.loading.merge_runtime import SourceMergeStrategy
from dature.masking.masking import mask_field_origins, mask_json_value, mask_source_entries
from dature.report_types import FieldOrigin, SourceEntry
from dature.type_aliases import JSONValue

logger = logging.getLogger("dature")

_REPORT_ATTR = "__dature_load_report__"


# --8<-- [start:report-structure]
@dataclass(frozen=True, slots=True, kw_only=True)
class LoadReport:
    dataclass_name: str
    strategy: SourceMergeStrategy | None
    sources: tuple[SourceEntry, ...]
    field_origins: tuple[FieldOrigin, ...]
    merged_data: JSONValue


# --8<-- [end:report-structure]


# --8<-- [start:load-report]
def load_report(instance: Any) -> LoadReport | None:  # noqa: ANN401
    report = getattr(instance, _REPORT_ATTR, None)
    if isinstance(report, LoadReport):
        return report
    warnings.warn(
        "To get LoadReport, pass debug=True to load()",
        stacklevel=2,
    )
    return None


# --8<-- [end:load-report]


def attach_load_report(target: Any, report: LoadReport) -> None:  # noqa: ANN401
    setattr(target, _REPORT_ATTR, report)


def build_single_source_report(
    *,
    dataclass_name: str,
    loader_type: str,
    file_path: str | None,
    raw_data: JSONValue,
    masking: MaskingConfig,
    secret_paths: frozenset[str] = frozenset(),
) -> LoadReport:
    raw_data = mask_json_value(raw_data, secret_paths=secret_paths, masking=masking)

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


def build_merge_report(  # noqa: PLR0913
    *,
    dataclass_name: str,
    strategy: SourceMergeStrategy,
    source_entries: tuple[SourceEntry, ...],
    field_origins: tuple[FieldOrigin, ...],
    merged_data: JSONValue,
    masking: MaskingConfig,
    secret_paths: frozenset[str] = frozenset(),
) -> LoadReport:
    source_entries = mask_source_entries(source_entries, secret_paths=secret_paths, masking=masking)
    field_origins = mask_field_origins(field_origins, secret_paths=secret_paths, masking=masking)
    merged_data = mask_json_value(merged_data, secret_paths=secret_paths, masking=masking)

    return LoadReport(
        dataclass_name=dataclass_name,
        strategy=strategy,
        sources=source_entries,
        field_origins=field_origins,
        merged_data=merged_data,
    )
