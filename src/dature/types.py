import types
from collections.abc import Callable
from io import BufferedIOBase, RawIOBase, TextIOBase
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self
from urllib.parse import ParseResult

if TYPE_CHECKING:
    from dature.field_path import FieldPath
    from dature.protocols import ValidatorProtocol

type JSONValue = dict[str, JSONValue] | list[JSONValue] | str | int | float | bool | None


class NotLoaded:
    _instance: "NotLoaded | None" = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value]

    def __repr__(self) -> str:
        return "NOT_LOADED"

    def __bool__(self) -> bool:
        return False

    def __hash__(self) -> int:
        return hash("NOT_LOADED")


NOT_LOADED = NotLoaded()

type ProbeValue = dict[str, ProbeValue] | list[ProbeValue] | str | int | float | bool | NotLoaded | None

type ProbeDict = dict[str, ProbeValue]

# Result of get_type_hints() / get_args(): concrete class or parameterized generic
type TypeAnnotation = type[object] | types.GenericAlias

# Examples: "app", "app.database", "app.database.host"
type DotSeparatedPath = Annotated[str, "Dot-separated path for nested dictionary navigation"]

type NameStyle = Literal[
    "lower_snake",
    "upper_snake",
    "lower_camel",
    "upper_camel",
    "lower_kebab",
    "upper_kebab",
]

# Keys are FieldPath at runtime, but F[Type].field returns the field's static type (str, int, etc.)
# due to the overload trick for IDE autocompletion, so we accept those types here too.
type _FieldMappingKey = "FieldPath | str | int | float | bool | None"
type FieldMapping = dict[_FieldMappingKey, str | tuple[str, ...]]

type URL = ParseResult

type Base64UrlBytes = bytes
type Base64UrlStr = str

type ExpandEnvVarsMode = Literal["disabled", "default", "empty", "strict"]

type _ValidatorKey = "FieldPath | str | int | float | bool | None"
type FieldValidators = dict[_ValidatorKey, "ValidatorProtocol | tuple[ValidatorProtocol, ...]"]

type FieldMergeCallable = Callable[[list[JSONValue]], JSONValue]

type FileLike = TextIOBase | BufferedIOBase | RawIOBase
FILE_LIKE_TYPES: Final = (TextIOBase, BufferedIOBase, RawIOBase)
TEXT_IO_TYPES: Final = TextIOBase
BINARY_IO_TYPES: Final = (BufferedIOBase, RawIOBase)
type FileOrStream = Path | FileLike
type FilePath = str | Path
