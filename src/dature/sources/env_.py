import io
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, cast

from dature.errors import CaretSpan, LineRange, SourceLocation
from dature.sources.base import FileFieldMixin, FlatKeySource
from dature.types import (
    BINARY_IO_TYPES,
    TEXT_IO_TYPES,
    FileLike,
    FilePath,
    JSONValue,
    NestedConflict,
    NestedConflicts,
    NestedResolve,
    NestedResolveStrategy,
)


@dataclass(kw_only=True, repr=False)
class EnvSource(FlatKeySource):
    format_name = "env"
    location_label: ClassVar[str] = "ENV"

    def _load(self) -> JSONValue:
        return cast("JSONValue", os.environ)

    def resolve_location(
        self,
        *,
        field_path: list[str],
        file_content: str | None,  # noqa: ARG002
        nested_conflict: NestedConflict | None,
        input_value: JSONValue = None,  # noqa: ARG002
    ) -> list[SourceLocation]:
        var_name = self._resolve_var_name(field_path, self.prefix, self.nested_sep, nested_conflict)
        env_var_value: str | None = None
        if nested_conflict is not None:
            json_var = self._resolve_var_name(field_path[:1], self.prefix, self.nested_sep, None)
            if nested_conflict.used_var == json_var:
                env_var_value = nested_conflict.json_raw_value
        else:
            env_var_value = os.environ.get(var_name)
        line_content: list[str] | None = None
        line_carets: list[CaretSpan] | None = None
        if env_var_value is not None:
            value_lines = env_var_value.split("\n")
            value_start = len(var_name) + 1  # after "VAR_NAME="
            line_content = [f"{var_name}={value_lines[0]}", *value_lines[1:]]
            line_carets = [CaretSpan(start=value_start, end=value_start + len(value_lines[0]))]
            line_carets.extend(CaretSpan(start=0, end=len(line)) for line in value_lines[1:])
        return [
            SourceLocation(
                location_label=self.location_label,
                file_path=None,
                line_range=None,
                line_content=line_content,
                env_var_name=var_name,
                env_var_value=env_var_value,
                line_carets=line_carets,
            ),
        ]

    def _pre_process_row(
        self,
        key: str,
        value: str,
        result: dict[str, JSONValue],
        conflicts: NestedConflicts,
        *,
        resolved_nested_strategy: NestedResolveStrategy = "flat",
        resolved_nested_resolve: NestedResolve | None = None,
    ) -> None:
        if self.prefix and not key.startswith(self.prefix):
            return

        processed_key = key[len(self.prefix) :] if self.prefix else key
        processed_key = processed_key.lower()

        parts = processed_key.split(self.nested_sep)
        self._process_key_value(
            parts=parts,
            value=value,
            result=result,
            conflicts=conflicts,
            resolved_nested_strategy=resolved_nested_strategy,
            resolved_nested_resolve=resolved_nested_resolve,
        )


@dataclass(kw_only=True, repr=False)
class EnvFileSource(FileFieldMixin, EnvSource):
    format_name = "envfile"
    location_label: ClassVar[str] = "ENV FILE"
    file: "FileLike | FilePath" = ".env"

    def __repr__(self) -> str:
        display = self.format_name
        file_path_display = self.file_display()
        if file_path_display is not None:
            return f"{display} '{file_path_display}'"
        return display

    def resolve_location(
        self,
        *,
        field_path: list[str],
        file_content: str | None,
        nested_conflict: NestedConflict | None,
        input_value: JSONValue = None,
    ) -> list[SourceLocation]:
        var_name = self._resolve_var_name(field_path, self.prefix, self.nested_sep, nested_conflict)
        file_path = self.file_path_for_errors()
        line_range: LineRange | None = None
        line_content: list[str] | None = None
        line_carets: list[CaretSpan] | None = None
        if file_content is not None:
            line_range, line_content = _find_env_line(file_content, var_name)
        if line_content is not None and len(line_content) == 1:
            line = line_content[0]
            eq_pos = line.find("=")
            caret = CaretSpan(start=0, end=0)
            if eq_pos != -1:
                search_from = eq_pos + 1
                if input_value is not None:
                    found = self._find_value_in_line(
                        line,
                        input_value=input_value,
                        field_key=field_path[-1] if field_path else None,
                        search_from=search_from,
                    )
                    if found is not None:
                        caret = found
                else:
                    caret = CaretSpan(start=search_from, end=len(line))
            line_carets = [caret]
        return [
            SourceLocation(
                location_label=self.location_label,
                file_path=file_path,
                line_range=line_range,
                line_content=line_content,
                env_var_name=var_name,
                line_carets=line_carets,
            ),
        ]

    def _load(self) -> JSONValue:
        """Parse .env file into a flat key=value dict (before nesting/expand/parse)."""
        raw_pairs: dict[str, JSONValue] = {}

        if isinstance(self.file, TEXT_IO_TYPES):
            self._collect_pairs(self.file, raw_pairs)
        elif isinstance(self.file, BINARY_IO_TYPES):
            wrapper = io.TextIOWrapper(cast("io.BufferedReader", self.file))
            self._collect_pairs(wrapper, raw_pairs)
        else:
            path = self._resolved_file_path
            if path is None:
                msg = f"Config file not found: {self.file}"
                raise FileNotFoundError(msg)
            with path.open() as f:
                self._collect_pairs(f, raw_pairs)

        return raw_pairs

    @staticmethod
    def _collect_pairs(
        lines: Iterable[str],
        pairs: dict[str, JSONValue],
    ) -> None:
        for raw_line in lines:
            if not (line := raw_line.strip()) or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            _min_quoted_len = 2
            if len(value) >= _min_quoted_len and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            pairs[key] = value


def _find_env_line(content: str, var_name: str) -> tuple[LineRange | None, list[str] | None]:
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key == var_name:
            return LineRange(start=i, end=i), [stripped]
    return None, None
