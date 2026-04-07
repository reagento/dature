"""Custom source — subclass Source to read XML files."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from adaptix import Provider, loader

import dature
from dature.loaders import bool_loader, float_from_string
from dature.sources.base import FileSource
from dature.types import FileOrStream, JSONValue

SOURCES_DIR = Path(__file__).parent / "sources"


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
