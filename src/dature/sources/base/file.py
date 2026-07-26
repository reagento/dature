"""File-based source base classes: ``FileFieldMixin`` and ``FileSource``."""

import abc
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from dature.config_paths import find_config
from dature.errors import CaretSpan, LineRange, SourceLocation
from dature.expansion.env_expand import expand_file_path
from dature.refs import TEMPLATE_SUPPORTED, Template, template_to_str  # type: ignore[attr-defined]
from dature.sources.base.source import Source
from dature.sources.presentation import (
    build_search_path,
    empty_location,
    find_parent_line_range,
    strip_common_indent,
)
from dature.type_aliases import (
    FILE_LIKE_TYPES,
    FileLike,
    FileOrStream,
    FilePath,
    JSONValue,
    NestedConflict,
    SystemConfigDirsArg,
)


# --8<-- [start:file-source]
@dataclass(kw_only=True, repr=False)
class FileFieldMixin:
    file: "FileLike | FilePath | None" = None
    search_system_paths: bool | None = None
    system_config_dirs: "SystemConfigDirsArg | None" = None
    encoding: str | None = None
    skip_if_broken: bool | None = None
    skip_if_missing: bool | None = None
    resolved_file_path: Path | None = field(init=False, default=None)
    # --8<-- [end:file-source]

    def __post_init__(self) -> None:
        next_post_init = getattr(super(), "__post_init__", None)
        if next_post_init is not None:
            next_post_init()

        # Convert t-string Template to string (Python 3.14+).
        if TEMPLATE_SUPPORTED and isinstance(self.file, Template):
            self.file = template_to_str(self.file)  # pyright: ignore[reportArgumentType]
        if isinstance(self.file, (str, Path)):
            self.file = expand_file_path(self.file, mode="strict")
        self.resolved_file_path = self._compute_resolved_file_path()

    def _compute_resolved_file_path(self) -> Path | None:
        if self.file is None or isinstance(self.file, FILE_LIKE_TYPES):
            return None

        file_path = self.file if isinstance(self.file, Path) else Path(self.file)
        if file_path.exists():
            return file_path

        if self.search_system_paths:
            return find_config(file_path.name, self.system_config_dirs)

        return None

    @staticmethod
    def resolve_file_field(file: "FileLike | FilePath | None") -> FileOrStream:
        if isinstance(file, FILE_LIKE_TYPES):
            return file
        if file is not None:
            return Path(file)
        return Path()

    @staticmethod
    def file_field_display(file: "FileLike | FilePath | None") -> str | None:
        if isinstance(file, FILE_LIKE_TYPES):
            return "<stream>"
        if file is not None:
            return str(file)
        return None

    @staticmethod
    def file_field_path_for_errors(file: "FileLike | FilePath | None") -> Path | None:
        if isinstance(file, FILE_LIKE_TYPES):
            return None
        if file is not None:
            return Path(file)
        return None

    def file_display(self) -> str | None:
        if self.resolved_file_path is not None:
            return str(self.resolved_file_path)
        return self.file_field_display(self.file)

    def file_path_for_errors(self) -> Path | None:
        if self.resolved_file_path is not None:
            return self.resolved_file_path
        return self.file_field_path_for_errors(self.file)

    def display_name(self) -> str:
        return self.file_display() or self.format_name  # type: ignore[attr-defined]


@dataclass(kw_only=True, repr=False)
class FileSource(FileFieldMixin, Source, abc.ABC):
    location_label: str = "FILE"

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
        nested_conflict: NestedConflict | None,  # noqa: ARG002
        input_value: JSONValue = None,
        loaded_data: "JSONValue | None" = None,  # noqa: ARG002
    ) -> list[SourceLocation]:
        file_path = self.file_path_for_errors()
        file_content: str | None = None
        if file_path is not None:
            with suppress(OSError, UnicodeDecodeError):
                file_content = file_path.read_text(encoding=self.encoding)
        if file_content is None or not field_path:
            return [empty_location(self.location_label, file_path)]

        search_path = build_search_path(field_path, self.prefix)
        line_index = self.build_line_index(file_content)
        if line_index is None:
            return [empty_location(self.location_label, file_path)]

        line_range: LineRange | None = line_index.get(tuple(search_path))
        if line_range is None:
            line_range = find_parent_line_range(line_index, search_path)
        if line_range is None:
            return [empty_location(self.location_label, file_path)]

        lines = file_content.splitlines()
        content_lines: list[str] | None = None
        line_carets: list[CaretSpan] | None = None
        if 0 < line_range.start <= len(lines):
            end = min(line_range.end, len(lines))
            raw = lines[line_range.start - 1 : end]
            content_lines = strip_common_indent(raw)
            field_key = field_path[-1] if field_path else None
            line_carets = self.compute_line_carets(
                content_lines,
                input_value=input_value,
                field_key=field_key,
            )

        return [
            SourceLocation(
                location_label=self.location_label,
                file_path=file_path,
                line_range=line_range,
                line_content=content_lines,
                env_var_name=None,
                line_carets=line_carets,
            ),
        ]

    def _load(self) -> JSONValue:
        if isinstance(self.file, FILE_LIKE_TYPES):
            return self._load_file(self.file)

        path = self.resolved_file_path
        if path is None:
            msg = f"Config file not found: {self.file}"
            raise FileNotFoundError(msg)

        return self._load_file(path)

    @abc.abstractmethod
    def _load_file(self, path: FileOrStream) -> JSONValue: ...
