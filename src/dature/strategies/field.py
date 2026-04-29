from typing import Protocol, runtime_checkable

from dature.errors import DatureConfigError, SourceLoadError
from dature.types import FieldMergeStrategyName, JSONValue


# --8<-- [start:field-merge-strategy]
@runtime_checkable
class FieldMergeStrategy(Protocol):
    def __call__(self, values: list[JSONValue]) -> JSONValue: ...


# --8<-- [end:field-merge-strategy]


def _ensure_all_lists(values: list[JSONValue], strategy_name: str) -> list[list[JSONValue]]:
    out: list[list[JSONValue]] = []
    for v in values:
        if not isinstance(v, list):
            msg = f"{strategy_name} strategy requires every value to be a list, got {type(v).__name__}"
            raise TypeError(msg)
        out.append(v)
    return out


def _deduplicate(items: list[JSONValue]) -> list[JSONValue]:
    seen: list[JSONValue] = []
    for item in items:
        if not any(s == item for s in seen):
            seen.append(item)
    return seen


class FieldFirstWins:
    def __call__(self, values: list[JSONValue]) -> JSONValue:
        return values[0]


class FieldLastWins:
    def __call__(self, values: list[JSONValue]) -> JSONValue:
        return values[-1]


class FieldAppend:
    def __call__(self, values: list[JSONValue]) -> list[JSONValue]:
        result: list[JSONValue] = []
        for chunk in _ensure_all_lists(values, "APPEND"):
            result.extend(chunk)
        return result


class FieldAppendUnique:
    def __call__(self, values: list[JSONValue]) -> list[JSONValue]:
        result: list[JSONValue] = []
        for chunk in _ensure_all_lists(values, "APPEND_UNIQUE"):
            result.extend(chunk)
        return _deduplicate(result)


class FieldPrepend:
    def __call__(self, values: list[JSONValue]) -> list[JSONValue]:
        result: list[JSONValue] = []
        for chunk in reversed(_ensure_all_lists(values, "PREPEND")):
            result.extend(chunk)
        return result


class FieldPrependUnique:
    def __call__(self, values: list[JSONValue]) -> list[JSONValue]:
        result: list[JSONValue] = []
        for chunk in reversed(_ensure_all_lists(values, "PREPEND_UNIQUE")):
            result.extend(chunk)
        return _deduplicate(result)


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
