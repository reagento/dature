"""Type compatibility helpers for V-predicate applicability checks.

These helpers decide whether a given predicate (``V.len()``, ``V.each(...)``, ...)
can be applied to a specific field type. They are invoked from each predicate's
``check_type`` method at schema-build time, before any configuration data is read.
"""

import collections.abc
from typing import Annotated, Any, Union, get_args, get_origin


def strip_annotated(field_type: Any) -> Any:  # noqa: ANN401
    """Unwrap the outer ``Annotated[T, ...]``, returning ``T``. Non-Annotated types pass through."""
    if get_origin(field_type) is Annotated:
        return get_args(field_type)[0]
    return field_type


def get_concrete_origin(field_type: Any) -> type | None:  # noqa: ANN401
    """Resolve the concrete class behind a type annotation.

    Examples:
        ``list[str]`` -> ``list``
        ``tuple[int, ...]`` -> ``tuple``
        ``str`` -> ``str``
        ``int | str`` -> ``None`` (unions are not a single concrete class)
    """
    stripped = strip_annotated(field_type)
    origin = get_origin(stripped)
    if origin is None:
        return stripped if isinstance(stripped, type) else None
    if origin is Union:
        return None
    if isinstance(origin, type):
        return origin
    return None


def supports_len(field_type: Any) -> bool:  # noqa: ANN401
    origin = get_concrete_origin(field_type)
    return origin is not None and issubclass(origin, collections.abc.Sized)


def supports_iteration(field_type: Any) -> bool:  # noqa: ANN401
    origin = get_concrete_origin(field_type)
    return origin is not None and issubclass(origin, collections.abc.Iterable)


def supports_collection(field_type: Any) -> bool:  # noqa: ANN401
    """True when the type implements both ``__len__`` and ``__iter__`` (needed by V.unique_items)."""
    origin = get_concrete_origin(field_type)
    return origin is not None and issubclass(origin, collections.abc.Collection)


def is_str_type(field_type: Any) -> bool:  # noqa: ANN401
    origin = get_concrete_origin(field_type)
    return origin is str


def format_type(field_type: Any) -> str:  # noqa: ANN401
    """Render a type as a short name for use in error messages."""
    return getattr(field_type, "__name__", None) or repr(field_type)


def element_type_of(field_type: Any) -> Any:  # noqa: ANN401
    """Return ``T`` for ``list[T]`` / ``set[T]`` / ``frozenset[T]`` / ``tuple[T, ...]``.

    For fixed-arity tuples, unparameterized generics, or non-iterable types returns ``Any``.
    """
    stripped = strip_annotated(field_type)
    origin = get_origin(stripped)
    if origin in {list, set, frozenset}:
        args = get_args(stripped)
        return args[0] if args else Any
    if origin is tuple:
        match get_args(stripped):
            case (elem_type, rest) if rest is Ellipsis:
                return elem_type
            case _:
                return Any
    return Any
