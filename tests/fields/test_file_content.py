from collections.abc import Callable
from pathlib import Path

import pytest

from dature.fields.file_content import FileContent, FileMode, FileOptions


class TestFileContent:
    @pytest.mark.parametrize(
        ("mode", "options", "raw_content", "expected"),
        [
            ("r", FileOptions(), b"  value \n", "  value \n"),
            ("r", FileOptions(strip=True), b"  value \n", "value"),
            ("r", FileOptions(encoding="cp1251"), "привет".encode("cp1251"), "привет"),
            ("r", FileOptions(encoding="cp1251", strip=True), " привет\n".encode("cp1251"), "привет"),
            ("rb", FileOptions(), b"\x00\x01\x02", b"\x00\x01\x02"),
        ],
        ids=["default", "strip", "encoding", "encoding-and-strip", "binary"],
    )
    def test_data(
        self,
        tmp_path: Path,
        mode: FileMode,
        options: FileOptions,
        raw_content: bytes,
        expected: str | bytes,
    ) -> None:
        file = tmp_path / "secret.txt"
        file.write_bytes(raw_content)
        content = FileContent(file, options, mode=mode)

        result = content.data

        assert content.path == file
        assert result == expected

    @pytest.mark.parametrize(
        "make_path",
        [Path, str],
        ids=["path", "str"],
    )
    def test_path_is_normalized_to_path(self, tmp_path: Path, make_path: Callable[[Path], str | Path]) -> None:
        file = tmp_path / "secret.txt"

        content = FileContent(make_path(file))

        assert content.path == file

    @pytest.mark.parametrize(
        ("mode", "cache_data", "old", "new", "expected"),
        [
            ("r", False, b"old", b"new", "new"),
            ("r", True, b"old", b"new", "old"),
            ("rb", False, b"old", b"new", b"new"),
            ("rb", True, b"old", b"new", b"old"),
        ],
        ids=["text-no-cache", "text-cache", "bytes-no-cache", "bytes-cache"],
    )
    def test_data_cache(
        self,
        tmp_path: Path,
        mode: FileMode,
        cache_data: bool,
        old: bytes,
        new: bytes,
        expected: str | bytes,
    ) -> None:
        file = tmp_path / "secret.txt"
        file.write_bytes(old)
        content = FileContent(file, FileOptions(cache_data=cache_data), mode=mode)
        _ = content.data

        file.write_bytes(new)

        assert content.data == expected

    def test_cache_is_not_filled_when_first_read_fails(self, tmp_path: Path) -> None:
        file = tmp_path / "secret.txt"
        content = FileContent(file, FileOptions(cache_data=True))

        with pytest.raises(FileNotFoundError):
            _ = content.data
        file.write_text("value", encoding="utf-8")

        assert content.data == "value"

    def test_cache_does_not_affect_equality_and_hash(self, tmp_path: Path) -> None:
        file = tmp_path / "secret.txt"
        file.write_text("value", encoding="utf-8")
        options = FileOptions(cache_data=True)
        cached = FileContent(file, options)
        fresh = FileContent(file, options)
        _ = cached.data

        assert cached == fresh
        assert hash(cached) == hash(fresh)

    def test_strip_is_rejected_for_bytes(self, tmp_path: Path) -> None:
        file = tmp_path / "cert.bin"
        file.write_bytes(b"x")

        with pytest.raises(ValueError, match=r"^FileOptions\.strip is not supported for FileContent\[bytes\]$"):
            FileContent(file, FileOptions(strip=True), mode="rb")

    def test_repr_and_str_do_not_expose_content(self, tmp_path: Path) -> None:
        file = tmp_path / "secret.txt"
        file.write_text("super-secret", encoding="utf-8")
        content = FileContent(file)

        assert repr(content) == f"FileContent(path={str(file)!r})"
        assert str(content) == str(file)

    @pytest.mark.parametrize(
        ("make_other", "is_equal"),
        [
            (FileContent, True),
            (lambda file: FileContent(file, FileOptions(strip=True)), False),
            (lambda file: FileContent(file, FileOptions(cache_data=True)), False),
            (lambda file: FileContent(file, mode="rb"), False),
            (str, False),
        ],
        ids=["same", "other-options", "other-cache-data", "other-mode", "str"],
    )
    def test_equality(
        self,
        tmp_path: Path,
        make_other: Callable[[Path], object],
        is_equal: bool,
    ) -> None:
        file = tmp_path / "secret.txt"
        content = FileContent(file)

        result = content == make_other(file)

        assert result is is_equal
