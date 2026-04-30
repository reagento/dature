from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from json5 import JsonIdentifier


def str_from_json_identifier(value: "JsonIdentifier") -> str:
    return str(value)
