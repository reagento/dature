from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, overload

FileMode = Literal["r", "rb"]


@dataclass(frozen=True, slots=True)
class FileOptions:
    """Optional settings for ``FileContent``, passed through ``Annotated`` metadata.

    Attributes:
        encoding: Text encoding, used only for ``FileContent[str]``.
        strip: Strip surrounding whitespace from text content. Not allowed for ``FileContent[bytes]``.
        cache_data: Read the file on the first ``data`` access and reuse the result afterwards.
            By default the file is read on every access.
    """

    encoding: str = "utf-8"
    strip: bool = False
    cache_data: bool = False


def read_file_content(path: Path, mode: FileMode, options: FileOptions) -> str | bytes:
    """Read *path* according to *mode* and *options*.

    Raises:
        OSError: If the file cannot be read.
        UnicodeDecodeError: If the text content does not match ``options.encoding``.
    """
    if mode == "rb":
        return path.read_bytes()

    text = path.read_text(encoding=options.encoding)
    if options.strip:
        return text.strip()
    return text


class FileContent[T: (str, bytes)]:
    """Path to an existing file whose content is read lazily.

    ``FileContent[str]`` (the default) reads in text mode, ``FileContent[bytes]`` in binary mode.
    By default the content is not stored: ``data`` reads the file on every access.
    With ``FileOptions(cache_data=True)`` it is read once, on the first ``data`` access.
    """

    __slots__ = ("_cache", "_mode", "_options", "_path")

    @overload
    def __init__(
        self: "FileContent[str]",
        path: str | Path,
        options: FileOptions | None = None,
        *,
        mode: Literal["r"] = "r",
    ) -> None: ...

    @overload
    def __init__(
        self: "FileContent[bytes]",
        path: str | Path,
        options: FileOptions | None = None,
        *,
        mode: Literal["rb"],
    ) -> None: ...

    def __init__(
        self,
        path: str | Path,
        options: FileOptions | None = None,
        *,
        mode: FileMode = "r",
    ) -> None:
        resolved_options = options if options is not None else FileOptions()
        if mode == "rb" and resolved_options.strip:
            msg = "FileOptions.strip is not supported for FileContent[bytes]"
            raise ValueError(msg)

        self._path = Path(path)
        self._mode: FileMode = mode
        self._options = resolved_options
        self._cache: str | bytes | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def data(self) -> T:
        if self._cache is not None:
            return cast("T", self._cache)

        content = read_file_content(self._path, self._mode, self._options)
        if self._options.cache_data:
            self._cache = content
        return cast("T", content)

    def __str__(self) -> str:
        return str(self._path)

    def __repr__(self) -> str:
        return f"FileContent(path={str(self._path)!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileContent):
            return NotImplemented
        return (self._path, self._mode, self._options) == (other._path, other._mode, other._options)

    def __hash__(self) -> int:
        return hash((self._path, self._mode, self._options))
