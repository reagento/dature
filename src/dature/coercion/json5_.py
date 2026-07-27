try:
    from json5 import JsonIdentifier  # pyright: ignore[reportAssignmentType]
except ImportError:  # pragma: no cover  -- ``json5`` extra not installed

    class JsonIdentifier(str):  # type: ignore[no-redef]
        __slots__ = ()


def str_from_json_identifier(value: JsonIdentifier) -> str:
    return str(value)
