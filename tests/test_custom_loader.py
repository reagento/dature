"""Tests for custom loaders — subclassing BaseLoader."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from adaptix import Provider, loader

from dature import LoadMetadata, load
from dature.sources_loader.base import BaseLoader
from dature.sources_loader.loaders import bool_loader, float_from_string
from dature.types import FileOrStream, JSONValue


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
class XmlConfig:
    host: str
    port: int
    debug: bool


class TestCustomLoader:
    def test_xml_loader(self, tmp_path: Path) -> None:
        xml_file = tmp_path / "config.xml"
        xml_file.write_text(
            "<config>\n    <host>localhost</host>\n    <port>9090</port>\n    <debug>true</debug>\n</config>\n",
        )

        result = load(
            LoadMetadata(file_=xml_file, loader=XmlLoader),
            XmlConfig,
        )

        assert result.host == "localhost"
        assert result.port == 9090
        assert result.debug is True
