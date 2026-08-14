import types
from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from functools import lru_cache
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from dature.config import config
from dature.field_path import FieldPath
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.type_aliases import FieldMapping, TypeAnnotation
from dature.type_utils import find_nested_dataclasses


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


def canonical_name(name: str) -> str:
    """Lowercase *name* and strip ``-``/``_`` so it compares equal across ``NameStyle`` variants.

    Dots are preserved as path separators, so this doubles as a path canonicalizer.
    """
    return name.lower().replace("-", "").replace("_", "")


@lru_cache(maxsize=128)
def canonical_secret_paths(secret_paths: frozenset[str]) -> frozenset[str]:
    return frozenset(canonical_name(path) for path in secret_paths)


@lru_cache(maxsize=128)
def canonical_secret_leaf_names(secret_paths: frozenset[str]) -> frozenset[str]:
    return frozenset(canonical_name(path.rpartition(".")[2]) for path in secret_paths)


def matches_secret_name(name: str) -> bool:
    """Whether *name* itself looks like a secret field name under the configured patterns."""
    return _matches_secret_pattern(name, config.masking.secret_field_names)


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


@lru_cache(maxsize=128)
def _compute_secret_paths(dataclass_type: type, extra_patterns: tuple[str, ...]) -> frozenset[str]:
    all_patterns = (*config.masking.secret_field_names, *extra_patterns)
    result: set[str] = set()
    _walk_dataclass_fields(dataclass_type, prefix="", all_patterns=all_patterns, result=result)
    return frozenset(result)


def _alias_secret_paths(
    paths: frozenset[str],
    field_mappings: Sequence[FieldMapping | None],
) -> frozenset[str]:
    canonical_paths = canonical_secret_paths(paths)
    result: set[str] = set()
    for field_mapping in field_mappings:
        if not field_mapping:
            continue
        for field_path_key, aliases in field_mapping.items():
            if not isinstance(field_path_key, FieldPath) or not field_path_key.parts:
                continue
            schema_path = ".".join(field_path_key.parts)
            if canonical_name(schema_path) not in canonical_paths:
                continue

            alias_tuple = (aliases,) if isinstance(aliases, str) else tuple(aliases)
            prefix_parts = field_path_key.parts[:-1]
            for alias in alias_tuple:
                result.add(alias)
                if prefix_parts:
                    result.add(".".join((*prefix_parts, alias)))
    return frozenset(result)


def build_secret_paths(
    dataclass_type: type,
    *,
    extra_patterns: tuple[str, ...] = (),
    field_mappings: Sequence[FieldMapping | None] = (),
) -> frozenset[str]:
    if not is_dataclass(dataclass_type):
        return frozenset()
    paths = _compute_secret_paths(dataclass_type, extra_patterns)
    if not field_mappings:
        return paths
    return paths | _alias_secret_paths(paths, field_mappings)
