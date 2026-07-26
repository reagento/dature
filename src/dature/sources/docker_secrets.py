from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from dature.errors import CaretSpan, SourceLocation
from dature.expansion.env_expand import expand_file_path
from dature.sources.base import FlatKeySource
from dature.type_aliases import FilePath, JSONValue, NestedConflict


@dataclass(kw_only=True, repr=False)
class DockerSecretsSource(FlatKeySource):
    dir_: FilePath
    encoding: str | None = None
    skip_if_broken: bool | None = None
    skip_if_missing: bool | None = None
    format_name: str = "docker_secrets"
    location_label: str = "SECRET FILE"

    def __post_init__(self) -> None:
        if isinstance(self.dir_, (str, Path)):
            self.dir_ = expand_file_path(self.dir_, mode="strict")

    def __repr__(self) -> str:
        return f"{self.format_name} '{self.dir_}'"

    def display_name(self) -> str:
        return self.file_display() or self.format_name

    def file_display(self) -> str | None:
        return str(self.dir_)

    def file_path_for_errors(self) -> Path | None:
        return Path(self.dir_)

    def resolve_location(
        self,
        *,
        field_path: list[str],
        nested_conflict: NestedConflict | None,
        input_value: JSONValue = None,
        loaded_data: JSONValue | None = None,  # noqa: ARG002
    ) -> list[SourceLocation]:
        if nested_conflict is not None:
            json_var = self._resolve_var_name(field_path[:1], self.prefix, self.nested_sep, None)
            if nested_conflict.used_var == json_var:
                secret_name = field_path[0]
            else:
                secret_name = self.nested_sep.join(field_path)
        else:
            secret_name = self.nested_sep.join(field_path)
        if self.prefix is not None:
            secret_name = self.prefix + secret_name
        secret_file = Path(self.dir_) / secret_name
        line_content: list[str] | None = None
        line_carets: list[CaretSpan] | None = None
        with suppress(OSError):
            raw = secret_file.read_text(encoding=self.encoding).strip()
            if raw:
                value_lines = raw.split("\n")
                value_start = len(secret_name) + 3  # after "name = "
                line_content = [f"{secret_name} = {value_lines[0]}", *value_lines[1:]]
                first_caret = None
                if input_value is not None and len(value_lines) == 1:
                    first_caret = self._find_value_in_line(
                        line_content[0],
                        input_value=input_value,
                        field_key=field_path[-1] if field_path else None,
                        search_from=value_start,
                    )
                line_carets = self._value_line_carets(value_lines, value_start, first_caret)
        return [
            SourceLocation(
                location_label=self.location_label,
                file_path=secret_file,
                line_range=None,
                line_content=line_content,
                env_var_name=None,
                line_carets=line_carets,
            ),
        ]

    def _load(self) -> JSONValue:
        path = Path(self.dir_)

        result: dict[str, JSONValue] = {}
        for entry in sorted(path.iterdir()):
            if not entry.is_file():
                continue

            raw_name = entry.name
            value = entry.read_text(encoding=self.encoding).strip()

            # Absolute aliases bypass the prefix filter and are matched against the full name.
            absolute_mapped = self._alias_to_field_name(raw_name, absolute=True)
            if absolute_mapped is not None:
                result[absolute_mapped] = value
                continue

            if self.prefix and not raw_name.startswith(self.prefix):
                continue

            if self.prefix:
                raw_name = raw_name[len(self.prefix) :]

            mapped = self._alias_to_field_name(raw_name)
            key = mapped if mapped is not None else raw_name.lower()

            result[key] = value

        return result
