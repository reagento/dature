"""Tests for custom sources — subclassing Source."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from adaptix import Provider, loader

from dature import FileSource, load
from dature.loaders import bool_loader, float_from_string
from dature.types import FileOrStream, JSONValue


@dataclass(kw_only=True)
class XmlSource(FileSource):
    format_name: ClassVar[str] = "xml"
    path_finder_class = None

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
            XmlSource(file=xml_file),
            schema=XmlConfig,
        )

        assert result.host == "localhost"
        assert result.port == 9090
        assert result.debug is True
