"""File-based source base classes: ``FileFieldMixin`` and ``FileSource``."""

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from dature.config_paths import find_config
from dature.expansion.env_expand import expand_file_path
from dature.refs import TEMPLATE_SUPPORTED, Template, template_to_str  # type: ignore[attr-defined]
from dature.sources.base.source import Source
from dature.type_aliases import (
    FILE_LIKE_TYPES,
    FileLike,
    FileOrStream,
    FilePath,
    JSONValue,
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
        _super = super()
        if hasattr(_super, "__post_init__"):
            _super.__post_init__()

        # Convert t-string Template to string (Python 3.14+)
        if TEMPLATE_SUPPORTED and isinstance(self.file, Template):
            self.file = template_to_str(self.file)
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

    def encoding_for_errors(self) -> str | None:
        return self.encoding


@dataclass(kw_only=True, repr=False)
class FileSource(FileFieldMixin, Source, abc.ABC):
    location_label: ClassVar[str] = "FILE"

    def __repr__(self) -> str:
        display = self.format_name
        file_path_display = self.file_display()
        if file_path_display is not None:
            return f"{display} '{file_path_display}'"
        return display

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
