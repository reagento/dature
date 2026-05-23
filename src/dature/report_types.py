"""Frozen value types describing a load report.

``SourceEntry`` and ``FieldOrigin`` describe individual entries of a load
report. The aggregate ``LoadReport`` itself lives in :mod:`dature.load_report`
next to its helpers — keeping this module free of any ``merge_runtime``
import.
"""

from dataclasses import dataclass

from dature.types import JSONValue


# --8<-- [start:value-types]
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


# --8<-- [end:value-types]
