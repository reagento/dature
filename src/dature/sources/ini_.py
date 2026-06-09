import configparser
import io
import sys
from dataclasses import dataclass
from typing import cast

from adaptix.provider import Provider

from dature.errors import LineRange
from dature.expansion.env_expand import expand_env_vars
from dature.field_path import FieldPath
from dature.sources.base import string_value_loaders
from dature.sources.file_source import FileSource
from dature.types import BINARY_IO_TYPES, TEXT_IO_TYPES, ExpandEnvVarsMode, FileOrStream, JSONValue


@dataclass(kw_only=True, repr=False)
class IniSource(FileSource):
    format_name = "ini"

    def additional_loaders(self) -> list[Provider]:
        return string_value_loaders()

    def _pre_processing(
        self,
        data: JSONValue,
        *,
        resolved_expand: ExpandEnvVarsMode,
    ) -> JSONValue:
        prefixed = self._apply_prefix(data)
        expanded = expand_env_vars(prefixed, mode=resolved_expand)
        return self._parse_string_values(expanded)

    def _normalize_section(self, opts: dict[str, str]) -> dict[str, JSONValue]:
        # configparser has already lowercased all option names; match aliases case-insensitively
        result: dict[str, JSONValue] = {}
        for k, v in opts.items():
            field_name: str | None = None
            if self.field_mapping:
                for field_path, aliases in self.field_mapping.items():
                    if not isinstance(field_path, FieldPath):
                        continue
                    alias_list = (aliases,) if isinstance(aliases, str) else aliases
                    if any(a.lower() == k for a in alias_list) and field_path.parts:
                        field_name = field_path.parts[-1]
                        break
            result[field_name if field_name is not None else k] = v
        return result

    def _load_file(self, path: FileOrStream) -> JSONValue:
        config = configparser.ConfigParser(interpolation=None)
        if isinstance(path, TEXT_IO_TYPES):
            config.read_file(path)
        elif isinstance(path, BINARY_IO_TYPES):
            config.read_file(io.TextIOWrapper(cast("io.BufferedReader", path), encoding=self.encoding))
        else:
            with path.open(encoding=self.encoding) as f:
                config.read_file(f)
        if self.prefix and self.prefix in config:
            result: dict[str, JSONValue] = self._normalize_section(dict(config[self.prefix]))
            child_prefix = self.prefix + "."
            for section in config.sections():
                if section.startswith(child_prefix):
                    nested_key = section[len(child_prefix) :]
                    result[nested_key] = self._normalize_section(dict(config[section]))
            return {self.prefix: result}

        all_sections: dict[str, JSONValue] = {}
        if config.defaults():
            all_sections["DEFAULT"] = self._normalize_section(dict(config.defaults()))
        for section in config.sections():
            parts = section.split(".")
            target = all_sections
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = cast("dict[str, JSONValue]", target[part])
            target[parts[-1]] = self._normalize_section(dict(config[section]))
        return all_sections

    def build_line_index(self, content: str) -> dict[tuple[str, ...], LineRange] | None:
        parser = MetadataConfigParser()
        parser.read_string(content)
        result: dict[tuple[str, ...], LineRange] = {}
        for (section, option), line_range in parser.line_metadata.items():
            path = (*section.split("."), option)
            result[path] = line_range
        return result


if sys.version_info >= (3, 13):

    class MetadataConfigParser(configparser.ConfigParser):
        def __init__(self) -> None:
            super().__init__(interpolation=None)
            self.line_metadata: dict[tuple[str, str], LineRange] = {}

        def _handle_option(self, st: configparser._ReadState, line: configparser._Line, fpname: str) -> None:  # type: ignore[name-defined]
            super()._handle_option(st, line, fpname)
            if st.sectname is not None and st.optname is not None:
                self.line_metadata[(st.sectname, st.optname)] = LineRange(
                    start=st.lineno,
                    end=st.lineno,
                )

        def _handle_continuation_line(self, st: configparser._ReadState, line: configparser._Line, fpname: str) -> bool:  # type: ignore[name-defined]
            result = super()._handle_continuation_line(st, line, fpname)
            if result and st.sectname is not None and st.optname is not None:
                key = (st.sectname, st.optname)
                if key in self.line_metadata:
                    prev = self.line_metadata[key]
                    self.line_metadata[key] = LineRange(
                        start=prev.start,
                        end=st.lineno,
                    )
            return result

else:

    def _build_ini_line_map(content: str) -> dict[tuple[str, str], LineRange]:
        lines = content.splitlines()
        line_map: dict[tuple[str, str], LineRange] = {}
        current_section: str | None = None
        current_option: str | None = None
        indent_level = 0

        sectcre = configparser.ConfigParser.SECTCRE
        optcre = configparser.ConfigParser.OPTCRE
        nonspacecre = configparser.ConfigParser.NONSPACECRE
        comment_prefixes = ("#", ";")

        for lineno, raw_line in enumerate(lines, start=1):
            stripped = raw_line.strip()
            is_comment = False
            for prefix in comment_prefixes:
                if stripped.startswith(prefix):
                    is_comment = True
                    break
            if not stripped or is_comment:
                continue

            first_nonspace = nonspacecre.search(raw_line)
            cur_indent = first_nonspace.start() if first_nonspace else 0

            if current_section is not None and current_option is not None and cur_indent > indent_level:
                key = (current_section, current_option)
                if key in line_map:
                    prev = line_map[key]
                    line_map[key] = LineRange(start=prev.start, end=lineno)
                continue

            indent_level = cur_indent

            mo = sectcre.match(stripped)
            if mo:
                current_section = mo.group("header")
                current_option = None
                continue

            if current_section is None:
                continue

            mo = optcre.match(stripped)
            if mo:
                current_option = mo.group("option").rstrip().lower()
                line_map[(current_section, current_option)] = LineRange(start=lineno, end=lineno)

        return line_map

    class MetadataConfigParser(configparser.ConfigParser):
        def __init__(self) -> None:
            super().__init__(interpolation=None)
            self.line_metadata: dict[tuple[str, str], LineRange] = {}

        def read_string(self, string: str, source: str = "<string>") -> None:
            self.line_metadata = _build_ini_line_map(string)
            super().read_string(string, source)
