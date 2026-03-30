from enum import StrEnum


class MergeStrategyEnum(StrEnum):
    LAST_WINS = "last_wins"
    FIRST_WINS = "first_wins"
    FIRST_FOUND = "first_found"
    RAISE_ON_CONFLICT = "raise_on_conflict"


class FieldMergeStrategyEnum(StrEnum):
    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"
    APPEND = "append"
    APPEND_UNIQUE = "append_unique"
    PREPEND = "prepend"
    PREPEND_UNIQUE = "prepend_unique"
