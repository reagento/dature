import io
import os
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar, cast

from dature.errors.exceptions import LineRange, SourceLocation
from dature.sources_loader.flat_key import FlatKeyLoader
from dature.types import (
    BINARY_IO_TYPES,
    TEXT_IO_TYPES,
    FileOrStream,
    JSONValue,
    NestedConflict,
    NestedConflicts,
)


class EnvLoader(FlatKeyLoader):
    display_name = "env"
    display_label: ClassVar[str] = "ENV"

    def _load(self, _: FileOrStream) -> JSONValue:
        return cast("JSONValue", os.environ)

    @classmethod
    def resolve_location(
        cls,
        field_path: list[str],
        file_path: Path | None,  # noqa: ARG003
        file_content: str | None,  # noqa: ARG003
        prefix: str | None,
        split_symbols: str,
        nested_conflict: NestedConflict | None,
    ) -> list[SourceLocation]:
        var_name = cls._resolve_var_name(field_path, prefix, split_symbols, nested_conflict)
        env_var_value: str | None = None
        if nested_conflict is not None:
            json_var = cls._resolve_var_name(field_path[:1], prefix, split_symbols, None)
            if nested_conflict.used_var == json_var:
                env_var_value = nested_conflict.json_raw_value
        return [
            SourceLocation(
                display_label=cls.display_label,
                file_path=None,
                line_range=None,
                line_content=None,
                env_var_name=var_name,
                env_var_value=env_var_value,
            ),
        ]

    def _pre_process_row(
        self,
        key: str,
        value: str,
        result: dict[str, JSONValue],
        conflicts: NestedConflicts,
    ) -> None:
        if self._prefix and not key.startswith(self._prefix):
            return

        processed_key = key[len(self._prefix) :] if self._prefix else key
        processed_key = processed_key.lower()

        parts = processed_key.split(self._split_symbols)
        self._process_key_value(parts=parts, value=value, result=result, conflicts=conflicts)


class EnvFileLoader(EnvLoader):
    display_name = "envfile"
    display_label: ClassVar[str] = "ENV FILE"

    @classmethod
    def resolve_location(
        cls,
        field_path: list[str],
        file_path: Path | None,
        file_content: str | None,
        prefix: str | None,
        split_symbols: str,
        nested_conflict: NestedConflict | None,
    ) -> list[SourceLocation]:
        var_name = cls._resolve_var_name(field_path, prefix, split_symbols, nested_conflict)
        line_range: LineRange | None = None
        line_content: list[str] | None = None
        if file_content is not None:
            line_range, line_content = _find_env_line(file_content, var_name)
        return [
            SourceLocation(
                display_label=cls.display_label,
                file_path=file_path,
                line_range=line_range,
                line_content=line_content,
                env_var_name=var_name,
            ),
        ]

    def _load(self, path: FileOrStream) -> JSONValue:
        """Parse .env file into a flat key=value dict (before nesting/expand/parse)."""
        raw_pairs: dict[str, JSONValue] = {}

        if isinstance(path, TEXT_IO_TYPES):
            self._collect_pairs(path, raw_pairs)
        elif isinstance(path, BINARY_IO_TYPES):
            wrapper = io.TextIOWrapper(cast("io.BufferedReader", path))
            self._collect_pairs(wrapper, raw_pairs)
        else:
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
