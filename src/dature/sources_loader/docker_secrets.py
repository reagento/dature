from pathlib import Path
from typing import ClassVar

from dature.errors.exceptions import SourceLocation
from dature.sources_loader.flat_key import FlatKeyLoader
from dature.types import (
    FileOrStream,
    JSONValue,
    NestedConflict,
)


class DockerSecretsLoader(FlatKeyLoader):
    display_name = "docker_secrets"
    display_label: ClassVar[str] = "SECRET FILE"

    @classmethod
    def resolve_location(
        cls,
        field_path: list[str],
        file_path: Path | None,
        file_content: str | None,  # noqa: ARG003
        prefix: str | None,
        split_symbols: str,
        nested_conflict: NestedConflict | None,
    ) -> list[SourceLocation]:
        if nested_conflict is not None:
            json_var = cls._resolve_var_name(field_path[:1], prefix, split_symbols, None)
            if nested_conflict.used_var == json_var:
                secret_name = field_path[0]
            else:
                secret_name = split_symbols.join(field_path)
        else:
            secret_name = split_symbols.join(field_path)
        if prefix is not None:
            secret_name = prefix + secret_name
        secret_file = file_path / secret_name if file_path is not None else None
        return [
            SourceLocation(
                display_label=cls.display_label,
                file_path=secret_file,
                line_range=None,
                line_content=None,
                env_var_name=None,
            ),
        ]

    def _load(self, path: FileOrStream) -> JSONValue:
        if not isinstance(path, Path):
            msg = "DockerSecretsLoader does not support file-like objects"
            raise TypeError(msg)

        result: dict[str, JSONValue] = {}
        for entry in sorted(path.iterdir()):
            if not entry.is_file():
                continue

            key = entry.name.lower()
            value = entry.read_text().strip()

            if self._prefix and not key.startswith(self._prefix.lower()):
                continue

            if self._prefix:
                key = key[len(self._prefix) :]

            result[key] = value

        return result
