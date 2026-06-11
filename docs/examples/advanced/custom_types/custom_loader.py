from pathlib import Path
SOURCES_DIR = Path(__file__).parent / "sources"

# --8<-- [start:example]

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import dature
from dature.loaders import Provider, bool_loader, float_from_string, loader
from dature.sources.file_source import FileSource
from dature.type_aliases import FileOrStream, JSONValue


@dataclass(kw_only=True, repr=False)
class XmlSource(FileSource):
    format_name = "xml"

    def _load_file(self, path: FileOrStream) -> JSONValue:
        if not isinstance(path, Path):
            msg = "XmlSource only supports file paths"
            raise TypeError(msg)
        tree = ET.parse(path)  # noqa: S314
        root = tree.getroot()
        return {child.tag: child.text or "" for child in root}

    def additional_loaders(self) -> list[Provider]:
        return [
            loader(bool, bool_loader),
            loader(float, float_from_string),
        ]

    # Override _build_line_index(content) to add line-number diagnostics.
    # Return dict[tuple[str, ...], LineRange] mapping paths to line ranges,
    # or None to disable. See sources/yaml_.py for a reference.


@dataclass
class Config:
    host: str
    port: int
    debug: bool


config = dature.load(
    XmlSource(
        file=SOURCES_DIR / "custom_loader.xml",
    ),
    schema=Config,
)

assert config == Config(host="localhost", port=9090, debug=True)
# --8<-- [end:example]