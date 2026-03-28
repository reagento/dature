"""Custom loader — subclass BaseLoader to read XML files."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from adaptix import Provider, loader

from dature import Source, load
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.loaders import bool_loader, float_from_string
from dature.types import FileOrStream, JSONValue

SOURCES_DIR = Path(__file__).parent / "sources"


class XmlLoader(BaseLoader):
    display_name: ClassVar[str] = "xml"

    def _load(self, path: FileOrStream) -> JSONValue:
        if not isinstance(path, Path):
            msg = "XmlLoader only supports file paths"
            raise TypeError(msg)
        tree = ET.parse(path)  # noqa: S314
        root = tree.getroot()
        return {child.tag: child.text or "" for child in root}

    def _additional_loaders(self) -> list[Provider]:
        return [
            loader(bool, bool_loader),
            loader(float, float_from_string),
        ]


@dataclass
class Config:
    host: str
    port: int
    debug: bool


config = load(
    Source(
        file=SOURCES_DIR / "custom_loader.xml",
        loader=XmlLoader,
    ),
    Config,
)

assert config == Config(host="localhost", port=9090, debug=True)
