"""Generic helpers for traversing and mutating nested ``JSONValue`` dicts by dotted paths.

These are pure structural operations with no loading or validation logic.  Every function
accepts a ``JSONValue`` (which may be a non-dict at the top level) and returns a ``JSONValue``
or a list/tuple of results.

Dotted-path convention: ``"a.b.c"`` addresses ``data["a"]["b"]["c"]``.  A leading dot is
never used; an empty prefix means the root.
"""

from typing import Any

from dature.type_aliases import NOT_LOADED, JSONValue, ProbeDict

# Private sentinel used by `get_nested_value` to distinguish "key absent" from ``None``
# values stored under a key.
ABSENT = object()


def collect_leaf_paths(data: JSONValue, prefix: str = "") -> list[str]:
    """Return the dotted paths of every leaf (non-dict) node in *data*.

    Dict nodes are recursed into; everything else (including lists) is a leaf.
    An empty *prefix* means the root; the returned paths never start with a dot.
    """
    if not isinstance(data, dict):
        return [prefix] if prefix else []
    paths: list[str] = []
    for key, value in data.items():
        child_path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            paths.extend(collect_leaf_paths(value, child_path))
        else:
            paths.append(child_path)
    return paths


def flatten_dict(data: JSONValue, *, prefix: str = "") -> list[tuple[str, JSONValue]]:
    """Flatten a nested dict into ``(dotted_path, value)`` pairs for every leaf node.

    Dict nodes are recursed into; everything else is a leaf.  The *prefix* is prepended
    (with a ``.`` separator) when non-empty.  Returns an empty list for non-dict input.
    """
    if not isinstance(data, dict):
        return []
    result: list[tuple[str, JSONValue]] = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(flatten_dict(value, prefix=full_key))
        else:
            result.append((full_key, value))
    return result


def get_nested_value(data: JSONValue, dot_path: str) -> Any:  # noqa: ANN401
    """Return the value at *dot_path* inside *data*, or the private ``ABSENT`` sentinel.

    Callers that only need a boolean "present / absent" check should compare against
    ``nested_dict.ABSENT``; callers that need the value should guard with that sentinel
    before using the return value.

    Returns ``ABSENT`` when *data* is not a dict, when any intermediate key is missing,
    or when any intermediate value is not a dict.
    """
    if not isinstance(data, dict):
        return ABSENT
    parts = dot_path.split(".")
    current: JSONValue = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return ABSENT
        current = current[part]
    return current


def collect_field_values(raw_dicts: list[JSONValue], field_path: str) -> list[JSONValue]:
    """Return the values found at *field_path* in each dict in *raw_dicts*.

    Dicts that do not contain the path are silently skipped.
    """
    parts = field_path.split(".")
    values: list[JSONValue] = []
    for raw in raw_dicts:
        current: JSONValue = raw
        found = True
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                found = False
                break
            current = current[part]
        if found:
            values.append(current)
    return values


def set_nested_value(
    data: JSONValue,
    field_path: str,
    value: JSONValue,
) -> JSONValue:
    """Return a shallow copy of *data* with *value* written at *field_path*.

    Intermediate dicts are shallow-copied on the path; keys not on the path are shared.
    Returns *data* unchanged when it is not a dict or when an intermediate key is absent.
    """
    if not isinstance(data, dict):
        return data
    parts = field_path.split(".")
    if len(parts) == 1:
        result = dict(data)
        result[parts[0]] = value
        return result
    key = parts[0]
    rest = ".".join(parts[1:])
    result = dict(data)
    if key in result:
        result[key] = set_nested_value(result[key], rest, value)
    return result


def collect_not_loaded_paths(data: ProbeDict, prefix: str = "") -> list[str]:
    """Return dotted paths of every ``NOT_LOADED`` leaf inside *data*.

    Used by ``filter_invalid_fields`` after a skip-field probe to identify which
    fields failed coercion or validation.
    """
    paths: list[str] = []
    for key, value in data.items():
        current_path = f"{prefix}.{key}" if prefix else key
        if value is NOT_LOADED:
            paths.append(current_path)
        elif isinstance(value, dict):
            paths.extend(collect_not_loaded_paths(value, current_path))
    return paths


def remove_path_from_dict(data: dict[str, JSONValue], path: str) -> None:
    """Remove the leaf at *path* from *data* in-place, silently ignoring missing paths."""
    parts = path.split(".")
    current: dict[str, JSONValue] = data
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            return
        current = next_value
    current.pop(parts[-1], None)
