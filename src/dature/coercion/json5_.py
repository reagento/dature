try:
    from json5 import JsonIdentifier
except ImportError:  # pragma: no cover  -- ``json5`` extra not installed
    JsonIdentifier = str  # type: ignore[misc, assignment]


def str_from_json_identifier(value: JsonIdentifier) -> str:
    return str(value)
