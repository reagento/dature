"""Custom loader — subclass BaseLoader to read XML files."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from dature import LoadMetadata, load
from dature.sources_loader.base import BaseLoader
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


@dataclass
class Config:
    host: str
    port: int
    debug: bool


config = load(
    LoadMetadata(
        file_=SOURCES_DIR / "custom_loader.xml",
        loader=XmlLoader,
    ),
    Config,
)

print(config)
# Config(host='localhost', port=9090, debug=True)
