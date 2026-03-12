import configparser
import sys

from dature.errors.exceptions import LineRange
from dature.path_finders.base import PathFinder

_MIN_INI_PATH_DEPTH = 2


class TablePathFinder(PathFinder):
    def __init__(self, content: str) -> None:
        parser = MetadataConfigParser()
        parser.read_string(content)
        self._line_map = parser.line_metadata

    def find_line_range(self, target_path: list[str]) -> LineRange | None:
        if len(target_path) < _MIN_INI_PATH_DEPTH:
            return None
        section = ".".join(target_path[:-1])
        option = target_path[-1]
        return self._line_map.get((section, option))


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

    def _build_line_map(content: str) -> dict[tuple[str, str], LineRange]:
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
            self.line_metadata = _build_line_map(string)
            super().read_string(string, source)
