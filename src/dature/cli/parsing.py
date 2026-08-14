import argparse
import importlib
import json
import re
import types
import typing
from collections.abc import Sequence
from dataclasses import field, make_dataclass
from functools import cache
from typing import Any, Literal, Protocol, get_args, get_origin, get_type_hints

from dature._deprecations import resolve_deprecated_mask_secrets
from dature.field_path import F, _FieldAny
from dature.main import load
from dature.protocols import DataclassInstance
from dature.sources.protocol import SourceProtocol

#: Deprecated alias for --masking-mode; removed in dature 1.3.
_LEGACY_MASK_FLAG = "mask_secrets"


class CliCommonArgs(DataclassInstance, Protocol):
    """Fields shared by every dature CLI subcommand."""

    schema: str
    source: list[str]


class CliInspectArgs(CliCommonArgs, Protocol):
    """Fields accessed on the ``inspect`` subcommand's args dataclass."""

    field: str | None
    format: str


class CliArgs(DataclassInstance, Protocol):
    """Top-level dataclass produced by :func:`derive_cli_schema`."""

    command: Literal["inspect", "validate"]
    inspect: CliInspectArgs | None
    validate: CliCommonArgs | None


CLI_LOAD_PARAMS: tuple[str, ...] = (
    "strategy",
    "skip_if_broken",
    "skip_if_missing",
    "skip_field_if_invalid",
    "expand_env_vars",
    "secret_field_names",
    "masking_mode",
)

_UNESCAPED_COMMA = re.compile(r"(?<!\\),")
_UNESCAPED_EQUALS = re.compile(r"(?<!\\)=")


def import_attr(path: str) -> Any:  # noqa: ANN401
    """Import an attribute from a 'module:attr' or 'module.attr' string.

    Nested attributes via dots after ':' are supported (e.g. 'pkg:Cls.inner').
    """
    if ":" in path:
        module_path, attr_path = path.split(":", 1)
    else:
        if "." not in path:
            msg = f"Invalid import path: {path!r} (expected 'module:attr' or 'module.attr')"
            raise ValueError(msg)
        module_path, attr_path = path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    obj: Any = module
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj


def split_escaped(text: str, sep: str, *, maxsplit: int = 0) -> list[str]:
    """Split ``text`` by an unescaped ``sep``; ``\\sep`` is unescaped to ``sep``."""
    match sep:
        case ",":
            pattern = _UNESCAPED_COMMA
        case "=":
            pattern = _UNESCAPED_EQUALS
        case _:
            msg = f"Unsupported separator: {sep!r}"
            raise ValueError(msg)
    parts = pattern.split(text, maxsplit=maxsplit)
    escaped = "\\" + sep
    return [p.replace(escaped, sep) for p in parts]


def parse_value(raw: str) -> Any:  # noqa: ANN401
    """Parse a value string: try ``json.loads`` first, fallback to plain string."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def parse_source_spec(spec: str) -> tuple[type[SourceProtocol], dict[str, Any]]:
    """Parse ``type=...,k=v,...`` into ``(SourceClass, kwargs)``.

    Escape commas and equals signs in values with ``\\,`` and ``\\=``.
    """
    pairs: dict[str, Any] = {}
    for part in split_escaped(spec, ","):
        if not part:
            continue
        kv = split_escaped(part, "=", maxsplit=1)
        if len(kv) != 2:  # noqa: PLR2004
            msg = f"Invalid source kwarg {part!r}: expected 'key=value'"
            raise ValueError(msg)
        key, value = kv
        if not key:
            msg = f"Empty key in source spec: {part!r}"
            raise ValueError(msg)
        if key in pairs:
            msg = f"Duplicate key {key!r} in source spec"
            raise ValueError(msg)
        pairs[key] = value if key == "type" else parse_value(value)

    type_path = pairs.pop("type", None)
    if type_path is None:
        msg = f"Missing required 'type=...' in source spec: {spec!r}"
        raise ValueError(msg)

    obj = import_attr(type_path)
    if not isinstance(obj, type):
        msg = f"'{type_path}' is not a class"
        raise TypeError(msg)
    return obj, pairs


def _resolve_alias(annotation: Any) -> Any:  # noqa: ANN401
    """Unwrap PEP 695 ``type X = ...`` aliases to their underlying value."""
    if isinstance(annotation, typing.TypeAliasType):
        return annotation.__value__
    return annotation


def _non_none_args(annotation: Any) -> tuple[Any, ...]:  # noqa: ANN401
    """Return non-``NoneType`` constituents of a union; otherwise wrap the annotation."""
    resolved = _resolve_alias(annotation)
    if get_origin(resolved) in (types.UnionType, typing.Union):
        return tuple(a for a in get_args(resolved) if a is not type(None))
    return (resolved,)


def _cli_field_type(annotation: Any) -> Any:  # noqa: ANN401
    """Narrow ``annotation`` to the type argparse will produce on the CLI.

    Mirrors candidate-selection in :func:`add_typed_arg`: returns the first
    union arm matching one of the supported categories (``bool``, ``Literal``,
    ``tuple[str, ...]``/``Sequence[str]``, ``str``, the ``F.ANY`` sentinel).
    Both ``tuple[str, ...]`` and ``Sequence[str]`` are downgraded to ``list[str]``
    because argparse ``action="append"`` produces a list. The ``F.ANY``
    sentinel arm (e.g. in ``skip_field_if_invalid``) becomes a plain ``bool``
    flag — the ``Sequence[FieldPath]`` arm is not CLI-expressible and is
    skipped.
    """
    for raw_cand in _non_none_args(annotation):
        cand = _resolve_alias(raw_cand)
        if cand is bool or cand is _FieldAny:
            return bool
        origin = get_origin(cand)
        if origin is Literal:
            return cand
        if origin in (tuple, Sequence):
            item_args = get_args(cand)
            if item_args and item_args[0] is str:
                return list[str]
        if cand is str:
            return str
    msg = f"Unsupported CLI annotation: {annotation!r}"
    raise TypeError(msg)


def add_typed_arg(parser: argparse.ArgumentParser, name: str, annotation: Any) -> None:  # noqa: ANN401
    """Add an argparse flag inferred from a Python type annotation.

    Supports: ``bool``, ``Literal[...]``, ``tuple[str, ...]``/``Sequence[str]``,
    ``str``, the ``F.ANY`` sentinel, and unions/aliases of these.
    """
    flag = f"--{name.replace('_', '-')}"
    for raw_cand in _non_none_args(annotation):
        cand = _resolve_alias(raw_cand)
        if cand is bool or cand is _FieldAny:
            parser.add_argument(flag, action="store_true", default=None)
            return
        origin = get_origin(cand)
        if origin is Literal:
            parser.add_argument(flag, choices=list(get_args(cand)), default=None)
            return
        if origin in (tuple, Sequence):
            item_args = get_args(cand)
            if item_args and item_args[0] is str:
                parser.add_argument(flag, action="append", default=None)
                return
        if cand is str:
            parser.add_argument(flag, default=None)
            return
    msg = f"Unsupported CLI annotation for {name!r}: {annotation!r}"
    raise TypeError(msg)


@cache
def _load_type_hints() -> dict[str, Any]:
    return get_type_hints(load)


def add_load_args(parser: argparse.ArgumentParser) -> None:
    """Generate CLI flags for ``load()`` parameters listed in ``CLI_LOAD_PARAMS``."""
    hints = _load_type_hints()
    for name in CLI_LOAD_PARAMS:
        if name not in hints:
            msg = f"{name!r} not found in load() signature"
            raise RuntimeError(msg)
        add_typed_arg(parser, name, hints[name])
    # Deprecated alias for --masking-mode, removed in dature 1.3.
    parser.add_argument(
        "--mask-secrets",
        action="store_true",
        default=None,
        help=argparse.SUPPRESS,
    )


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add ``--schema``, ``--source`` (repeatable) and ``load()`` flags to the parser."""
    parser.add_argument(
        "--schema",
        required=True,
        metavar="MODULE:ATTR",
        help="Import path to dataclass schema (e.g. myapp.config:Settings).",
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        metavar="SPEC",
        help=(
            "Source spec: 'type=Class,k=v,k=v'. "
            "Repeatable (order preserved). Use \\, and \\= to escape separators in values."
        ),
    )
    add_load_args(parser)


def build_load_kwargs_from_dataclass(args: DataclassInstance) -> dict[str, Any]:
    """Collect non-``None`` values for ``CLI_LOAD_PARAMS`` from a derived dataclass.

    Re-tuples list values whose ``load()`` annotation declares ``tuple[...]`` —
    the CLI schema downgrades ``tuple[str, ...]`` to ``list[str]`` (argparse
    ``action="append"`` produces a list and adaptix does not coerce list to
    tuple), so we have to undo that before calling ``load()``.

    Booleans on params whose annotation carries the ``F.ANY`` sentinel arm
    (e.g. ``skip_field_if_invalid``) are mapped ``True`` → ``F.ANY``, since the
    CLI flag for that arm is a plain ``store_true`` boolean.

    ``--mask-secrets`` is a deprecated alias for ``--masking-mode`` (removed in
    dature 1.3): when set, it warns and maps onto ``masking_mode``, which wins if
    also passed explicitly.
    """
    hints = _load_type_hints()
    result: dict[str, Any] = {}
    for name in CLI_LOAD_PARAMS:
        value = getattr(args, name, None)
        if value is None:
            continue
        if isinstance(value, list) and _orig_wants_tuple(hints[name]):
            value = tuple(value)
        elif isinstance(value, bool) and value and _orig_wants_field_any(hints[name]):
            value = F.ANY
        result[name] = value

    legacy_mask_secrets = getattr(args, _LEGACY_MASK_FLAG, None)
    if legacy_mask_secrets is not None:
        result["masking_mode"] = resolve_deprecated_mask_secrets(result.get("masking_mode"), legacy_mask_secrets)

    return result


def _orig_wants_tuple(annotation: Any) -> bool:  # noqa: ANN401
    """Return True if any non-None arm of ``annotation`` is ``tuple[...]``."""
    return any(get_origin(_resolve_alias(cand)) is tuple for cand in _non_none_args(annotation))


def _orig_wants_field_any(annotation: Any) -> bool:  # noqa: ANN401
    """Return True if any non-None arm of ``annotation`` is the ``F.ANY`` sentinel type."""
    return any(_resolve_alias(cand) is _FieldAny for cand in _non_none_args(annotation))


@cache
def derive_cli_schema() -> type:
    """Build the runtime dataclass schema for the dature CLI.

    Returns a top-level dataclass with a discriminated ``command`` field and
    nested dataclasses for the ``inspect`` and ``validate`` subcommands. The
    fields for ``load()`` parameters are derived from :func:`load`'s type
    hints, so the CLI stays in sync with the public API automatically.

    Cached: the same class is returned on every call so adaptix can reuse its
    Retort cache for repeated runs (e.g. test suites).
    """
    hints = _load_type_hints()
    common: list[tuple[str, Any, Any]] = [
        ("schema", str, field()),
        ("source", list[str], field()),
    ]
    for name in CLI_LOAD_PARAMS:
        if name not in hints:
            msg = f"{name!r} not found in load() signature"
            raise RuntimeError(msg)
        cli_type = _cli_field_type(hints[name])
        common.append((name, cli_type | None, field(default=None)))
    # Deprecated alias for --masking-mode, removed in dature 1.3.
    common.append((_LEGACY_MASK_FLAG, bool | None, field(default=None)))

    inspect_args = make_dataclass(
        "InspectArgs",
        [
            *common,
            ("field", str | None, field(default=None)),
            ("format", Literal["json", "text", "table"], field(default="json")),
        ],
    )
    validate_args = make_dataclass("ValidateArgs", common)
    return make_dataclass(
        "CliArgs",
        [
            ("command", Literal["inspect", "validate"], field()),
            ("inspect", inspect_args | None, field(default=None)),
            ("validate", validate_args | None, field(default=None)),
        ],
    )


def build_sources(specs: list[str]) -> list[SourceProtocol]:
    """Parse each spec and instantiate the corresponding Source."""
    sources: list[SourceProtocol] = []
    for spec in specs:
        klass, kwargs = parse_source_spec(spec)
        source = klass(**kwargs)
        if not isinstance(source, SourceProtocol):
            msg = f"{klass.__name__!r} is not a SourceProtocol implementation"
            raise TypeError(msg)
        sources.append(source)
    return sources
