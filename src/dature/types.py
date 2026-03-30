import types
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BufferedIOBase, RawIOBase, TextIOBase
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal, Self
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

# F[Type].field is FieldPath at runtime, but the overload trick makes mypy see the
# field's static type (str, int, list[str], dict, etc.) for IDE autocompletion.
# This union covers all types mypy can infer from F expressions.
type FieldRef = (
    "FieldPath | str | int | float | bool | list[Any] | dict[str, Any] | tuple[Any, ...] | set[Any] | bytes | None"
)

type FieldMapping = dict[FieldRef, str | tuple[str, ...]]

type URL = ParseResult

type Base64UrlBytes = bytes
type Base64UrlStr = str

type ExpandEnvVarsMode = Literal["disabled", "default", "empty", "strict"]

type NestedResolveStrategy = Literal["flat", "json"]
# Values are FieldPath at runtime, but F[Type] returns the dataclass type itself
# due to the overload trick for IDE autocompletion, so we accept Any here.
type _NestedResolveValue = "tuple[FieldPath | Any, ...]"
type NestedResolve = dict[NestedResolveStrategy, _NestedResolveValue]

type FieldValidators = dict[FieldRef, "ValidatorProtocol | tuple[ValidatorProtocol, ...]"]

type FieldMergeCallable = Callable[[list[JSONValue]], JSONValue]

type MergeStrategyName = Literal["last_wins", "first_wins", "first_found", "raise_on_conflict"]
type FieldMergeStrategyName = Literal["first_wins", "last_wins", "append", "append_unique", "prepend", "prepend_unique"]
type TypeLoaderMap = dict[type, Callable[..., Any]]
type FieldMergeMap = dict[FieldRef, "FieldMergeStrategyName | Callable[..., Any]"]
type FieldGroupTuple = tuple[FieldRef, ...]

type FileLike = TextIOBase | BufferedIOBase | RawIOBase
FILE_LIKE_TYPES: Final = (TextIOBase, BufferedIOBase, RawIOBase)
TEXT_IO_TYPES: Final = TextIOBase
BINARY_IO_TYPES: Final = (BufferedIOBase, RawIOBase)
type FileOrStream = Path | FileLike
type FilePath = str | Path


@dataclass(frozen=True, slots=True)
class NestedConflict:
    used_var: str
    ignored_var: str
    json_raw_value: str


type NestedConflicts = dict[str, NestedConflict]


@dataclass(frozen=True, slots=True)
class LoadRawResult:
    data: JSONValue
    nested_conflicts: NestedConflicts = field(default_factory=dict)
