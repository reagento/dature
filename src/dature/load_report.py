import logging
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dature.types import JSONValue

if TYPE_CHECKING:
    from dature.strategies.source import SourceMergeStrategy

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
    strategy: "SourceMergeStrategy | None"
    sources: tuple[SourceEntry, ...]
    field_origins: tuple[FieldOrigin, ...]
    merged_data: JSONValue


# --8<-- [end:report-structure]


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
