"""Frozen value types describing a location inside a source file.

Lives in its own module so that ``errors.exceptions`` (which embeds these in
exception objects) and ``errors.rendering`` (which formats them for display) can
share the same definitions without an import cycle. Public consumers continue
to import them via ``dature.errors`` thanks to the re-export there.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LineRange:
    start: int
    end: int

    def __repr__(self) -> str:
        if self.start == self.end:
            return f"line {self.start}"
        return f"line {self.start}-{self.end}"


@dataclass(frozen=True, slots=True)
class CaretSpan:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class SourceLocation:
    location_label: str
    file_path: Path | None
    line_range: LineRange | None
    line_content: list[str] | None
    env_var_name: str | None
    annotation: str | None = None
    env_var_value: str | None = None
    line_carets: list[CaretSpan] | None = None
