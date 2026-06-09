"""Frozen leaf value types for load reports.

Owns ``SourceEntry`` and ``FieldOrigin`` — the atomic entries that describe
individual sources and field origins within a report. Intentionally free of
any ``merge_runtime`` import (no cycle). The public aggregate
``LoadReport`` lives in :mod:`dature.load_report`; the internal accumulator
snapshot ``_LoadCtxSnapshot`` lives in :mod:`dature.loading.merge_runtime`.
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
