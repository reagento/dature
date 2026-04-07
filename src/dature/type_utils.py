from dataclasses import is_dataclass
from typing import Annotated, get_args, get_origin

from dature.types import TypeAnnotation


def find_nested_dataclasses(field_type: TypeAnnotation) -> list[type]:
    result: list[type] = []
    queue: list[TypeAnnotation] = [field_type]

    while queue:
        current = queue.pop()

        if is_dataclass(current) and isinstance(current, type):
            result.append(current)
            continue

        origin = get_origin(current)
        if origin is Annotated:
            queue.append(get_args(current)[0])
        elif origin is not None:
            queue.extend(get_args(current))

    return result
