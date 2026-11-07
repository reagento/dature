import re
from collections.abc import Callable
from dataclasses import make_dataclass
from pathlib import Path
from typing import Annotated, Any

import pytest
from adaptix import DebugTrail, Retort

from dature.fields.file_content import FileContent, FileOptions
from dature.providers.file_content import FileContentProvider


class TestFileContentProvider:
    @pytest.mark.parametrize(
        ("field_type", "raw_content", "expected_data"),
        [
            (FileContent, b"a\n", "a\n"),
            (FileContent[str], b"a\n", "a\n"),
            (FileContent[bytes], b"a\n", b"a\n"),
            (Annotated[FileContent[str], FileOptions(strip=True)], b"a\n", "a"),
            (Annotated[FileContent[str], FileOptions(encoding="cp1251")], "привет".encode("cp1251"), "привет"),
            (Annotated[FileContent[bytes], FileOptions()], b"a\n", b"a\n"),
            (Annotated[FileContent[str], FileOptions(cache_data=True)], b"a\n", "a\n"),
        ],
        ids=[
            "bare",
            "str",
            "bytes",
            "annotated-strip",
            "annotated-encoding",
            "annotated-bytes",
            "annotated-cache",
        ],
    )
    def test_loads_file_content(
        self,
        tmp_path: Path,
        field_type: Any,
        raw_content: bytes,
        expected_data: str | bytes,
    ) -> None:
        file = tmp_path / "secret.txt"
        file.write_bytes(raw_content)
        schema = make_dataclass("Cfg", [("cert", field_type)])
        retort = Retort(recipe=[FileContentProvider()])

        result: Any = retort.load({"cert": str(file)}, schema)

        assert result.cert.path == file
        assert result.cert.data == expected_data


def _missing(path: Path) -> Path:
    return path


def _directory(path: Path) -> Path:
    path.mkdir()
    return path


@pytest.mark.parametrize(
    "prepare",
    [_missing, _directory],
    ids=["missing", "directory"],
)
def test_loading_not_a_file_raises(tmp_path: Path, prepare: Callable[[Path], Path]) -> None:
    path = prepare(tmp_path / "target")
    schema = make_dataclass("Cfg", [("cert", FileContent)])
    retort = Retort(recipe=[FileContentProvider()], debug_trail=DebugTrail.DISABLE)

    with pytest.raises(ValueError, match=f"^{re.escape(f'File not found: {path}')}$") as exc_info:
        retort.load({"cert": str(path)}, schema)

    assert exc_info.value.input_value == str(path)
