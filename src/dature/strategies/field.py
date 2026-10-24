from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from dature.errors import DatureConfigError, SourceLoadError
from dature.type_aliases import FieldMergeStrategyName, JSONValue


# --8<-- [start:field-merge-strategy]
@dataclass(frozen=True, slots=True, kw_only=True)
class FieldMergeResult:
    """Merged value plus indices (into ``values``) of the entries that shaped it."""

    value: JSONValue
    contributors: Sequence[int]


@runtime_checkable
class FieldMergeStrategy(Protocol):
    def __call__(self, values: list[JSONValue]) -> "JSONValue | FieldMergeResult": ...


# --8<-- [end:field-merge-strategy]


def _ensure_all_lists(values: list[JSONValue], strategy_name: str) -> list[list[JSONValue]]:
    out: list[list[JSONValue]] = []
    for v in values:
        if not isinstance(v, list):
            msg = f"{strategy_name} strategy requires every value to be a list, got {type(v).__name__}"
            raise TypeError(msg)
        out.append(v)
    return out


def _nonempty_or_all(chunks: list[list[JSONValue]]) -> list[int]:
    nonempty = [i for i, chunk in enumerate(chunks) if chunk]
    return nonempty or list(range(len(chunks)))


def _deduplicate_chunks(
    chunks: list[list[JSONValue]],
    order: Sequence[int],
) -> FieldMergeResult:
    seen: list[JSONValue] = []
    contributors: set[int] = set()
    for idx in order:
        for item in chunks[idx]:
            if not any(s == item for s in seen):
                seen.append(item)
                contributors.add(idx)
    return FieldMergeResult(
        value=seen,
        contributors=sorted(contributors) or list(range(len(chunks))),
    )


class FieldFirstWins:
    def __call__(self, values: list[JSONValue]) -> FieldMergeResult:
        return FieldMergeResult(value=values[0], contributors=[0])


class FieldLastWins:
    def __call__(self, values: list[JSONValue]) -> FieldMergeResult:
        return FieldMergeResult(value=values[-1], contributors=[len(values) - 1])


class FieldAppend:
    def __call__(self, values: list[JSONValue]) -> FieldMergeResult:
        chunks = _ensure_all_lists(values, "APPEND")
        result: list[JSONValue] = []
        for chunk in chunks:
            result.extend(chunk)
        return FieldMergeResult(value=result, contributors=_nonempty_or_all(chunks))


class FieldAppendUnique:
    def __call__(self, values: list[JSONValue]) -> FieldMergeResult:
        chunks = _ensure_all_lists(values, "APPEND_UNIQUE")
        return _deduplicate_chunks(chunks, range(len(chunks)))


class FieldPrepend:
    def __call__(self, values: list[JSONValue]) -> FieldMergeResult:
        chunks = _ensure_all_lists(values, "PREPEND")
        result: list[JSONValue] = []
        for chunk in reversed(chunks):
            result.extend(chunk)
        return FieldMergeResult(value=result, contributors=_nonempty_or_all(chunks))


class FieldPrependUnique:
    def __call__(self, values: list[JSONValue]) -> FieldMergeResult:
        chunks = _ensure_all_lists(values, "PREPEND_UNIQUE")
        return _deduplicate_chunks(chunks, range(len(chunks) - 1, -1, -1))


_FIELD_BY_NAME: dict[FieldMergeStrategyName, type[FieldMergeStrategy]] = {
    "first_wins": FieldFirstWins,
    "last_wins": FieldLastWins,
    "append": FieldAppend,
    "append_unique": FieldAppendUnique,
    "prepend": FieldPrepend,
    "prepend_unique": FieldPrependUnique,
}


def resolve_field_strategy(
    s: "FieldMergeStrategyName | FieldMergeStrategy",
    *,
    dataclass_name: str = "<unknown>",
) -> FieldMergeStrategy:
    if isinstance(s, str):
        if s not in _FIELD_BY_NAME:
            available = ", ".join(_FIELD_BY_NAME)
            msg = f"invalid field merge strategy: {s!r}. Available: {available}"
            raise DatureConfigError(dataclass_name, [SourceLoadError(message=msg)])
        cls: type[FieldMergeStrategy] = _FIELD_BY_NAME[s]
        return cls()
    return s
