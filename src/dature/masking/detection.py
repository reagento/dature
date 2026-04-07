import types
from dataclasses import fields, is_dataclass
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from dature.config import config
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.type_utils import find_nested_dataclasses
from dature.types import TypeAnnotation

_secret_paths_cache: dict[tuple[type, tuple[str, ...]], frozenset[str]] = {}


def _is_secret_type(field_type: TypeAnnotation) -> bool:
    queue: list[TypeAnnotation] = [field_type]

    while queue:
        current = queue.pop()

        if current is SecretStr or current is PaymentCardNumber:
            return True

        origin = get_origin(current)
        if origin is Annotated:
            queue.append(get_args(current)[0])
        elif origin is Union or isinstance(current, types.UnionType):
            queue.extend(get_args(current))

    return False


def _matches_secret_pattern(name: str, patterns: tuple[str, ...]) -> bool:
    lower_name = name.lower()
    return any(pattern in lower_name for pattern in patterns)


def _walk_dataclass_fields(
    dataclass_type: type,
    *,
    prefix: str,
    all_patterns: tuple[str, ...],
    result: set[str],
) -> None:
    try:
        hints = get_type_hints(dataclass_type, include_extras=True)
    except Exception:  # noqa: BLE001
        return

    for field in fields(dataclass_type):
        field_name = field.name
        if prefix:
            full_path = f"{prefix}.{field_name}"
        else:
            full_path = field_name

        field_type = hints.get(field_name)
        if field_type is None:
            continue

        if _is_secret_type(field_type) or _matches_secret_pattern(field_name, all_patterns):
            result.add(full_path)

        nested_types = find_nested_dataclasses(field_type)
        for nested_dc in nested_types:
            _walk_dataclass_fields(
                nested_dc,
                prefix=full_path,
                all_patterns=all_patterns,
                result=result,
            )


def build_secret_paths(
    dataclass_type: type,
    *,
    extra_patterns: tuple[str, ...] = (),
) -> frozenset[str]:
    if not is_dataclass(dataclass_type):
        return frozenset()

    cache_key = (dataclass_type, extra_patterns)
    if cache_key in _secret_paths_cache:
        return _secret_paths_cache[cache_key]

    all_patterns = config.masking.secret_field_names + extra_patterns
    result: set[str] = set()

    _walk_dataclass_fields(
        dataclass_type,
        prefix="",
        all_patterns=all_patterns,
        result=result,
    )

    frozen = frozenset(result)
    _secret_paths_cache[cache_key] = frozen
    return frozen
