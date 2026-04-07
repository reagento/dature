from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from dature.errors import SourceLocation
from dature.expansion.env_expand import expand_file_path
from dature.sources.base import FlatKeySource
from dature.types import JSONValue, NestedConflict

if TYPE_CHECKING:
    from dature.types import FilePath


@dataclass(kw_only=True, repr=False)
class DockerSecretsSource(FlatKeySource):
    dir_: "FilePath"
    format_name = "docker_secrets"
    location_label: ClassVar[str] = "SECRET FILE"

    def __post_init__(self) -> None:
        if isinstance(self.dir_, (str, Path)):
            self.dir_ = expand_file_path(str(self.dir_), mode="strict")

    def __repr__(self) -> str:
        return f"{self.format_name} '{self.dir_}'"

    def file_display(self) -> str | None:
        return str(self.dir_)

    def file_path_for_errors(self) -> Path | None:
        return Path(self.dir_)

    @classmethod
    def resolve_location(
        cls,
        *,
        field_path: list[str],
        file_path: Path | None,
        file_content: str | None,  # noqa: ARG003
        prefix: str | None,
        nested_conflict: NestedConflict | None,
        split_symbols: str | None = None,
    ) -> list[SourceLocation]:
        resolved_symbols = split_symbols or "__"
        if nested_conflict is not None:
            json_var = cls._resolve_var_name(field_path[:1], prefix, resolved_symbols, None)
            if nested_conflict.used_var == json_var:
                secret_name = field_path[0]
            else:
                secret_name = resolved_symbols.join(field_path)
        else:
            secret_name = resolved_symbols.join(field_path)
        if prefix is not None:
            secret_name = prefix + secret_name
        secret_file = file_path / secret_name if file_path is not None else None
        return [
            SourceLocation(
                location_label=cls.location_label,
                file_path=secret_file,
                line_range=None,
                line_content=None,
                env_var_name=None,
            ),
        ]

    def _load(self) -> JSONValue:
        path = Path(self.dir_)

        result: dict[str, JSONValue] = {}
        for entry in sorted(path.iterdir()):
            if not entry.is_file():
                continue

            key = entry.name.lower()
            value = entry.read_text().strip()

            if self.prefix and not key.startswith(self.prefix.lower()):
                continue

            if self.prefix:
                key = key[len(self.prefix) :]

            result[key] = value

        return result
