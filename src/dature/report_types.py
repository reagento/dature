"""Frozen value types for ``LoadReport`` and related data.

Lives in its own module so that ``dature.load_report`` (which depends on
``dature.masking``) and ``dature.masking.masking`` (which needs ``FieldOrigin``
/ ``SourceEntry``) can share the same definitions without an import cycle.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dature.types import JSONValue

if TYPE_CHECKING:
    from dature.strategies.source import SourceMergeStrategy


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
