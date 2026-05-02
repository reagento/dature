import argparse
import importlib
import json
import re
import types
import typing
from dataclasses import field, make_dataclass
from functools import cache
from typing import Any, Literal, Protocol, get_args, get_origin, get_type_hints

from dature.main import load
from dature.protocols import DataclassInstance
from dature.sources.base import Source


class CliCommonArgs(DataclassInstance, Protocol):
    """Fields shared by every dature CLI subcommand."""

    schema: str
    source: list[str]


class CliInspectArgs(CliCommonArgs, Protocol):
    """Fields accessed on the ``inspect`` subcommand's args dataclass."""

    field: str | None
    format: str | None


class CliArgs(DataclassInstance, Protocol):
    """Top-level dataclass produced by :func:`derive_cli_schema`."""

    command: Literal["inspect", "validate"]
    inspect: CliInspectArgs | None
    validate: CliCommonArgs | None


CLI_LOAD_PARAMS: tuple[str, ...] = (
    "strategy",
    "skip_broken_sources",
    "skip_invalid_fields",
    "expand_env_vars",
    "secret_field_names",
    "mask_secrets",
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
    if sep == ",":
        pattern = _UNESCAPED_COMMA
    elif sep == "=":
        pattern = _UNESCAPED_EQUALS
    else:
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


def parse_source_spec(spec: str) -> tuple[type[Source], dict[str, Any]]:
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
    if not (isinstance(obj, type) and issubclass(obj, Source)):
        msg = f"{type_path!r} is not a subclass of dature.Source"
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
    ``tuple[str, ...]``, ``str``). ``tuple[str, ...]`` is downgraded to
    ``list[str]`` because argparse ``action="append"`` produces a list and
    adaptix does not coerce list to tuple.
    """
    for raw_cand in _non_none_args(annotation):
        cand = _resolve_alias(raw_cand)
        if cand is bool:
            return bool
        origin = get_origin(cand)
        if origin is Literal:
            return cand
        if origin is tuple:
            tuple_args = get_args(cand)
            if tuple_args and tuple_args[0] is str:
                return list[str]
        if cand is str:
            return str
    msg = f"Unsupported CLI annotation: {annotation!r}"
    raise TypeError(msg)


def add_typed_arg(parser: argparse.ArgumentParser, name: str, annotation: Any) -> None:  # noqa: ANN401
    """Add an argparse flag inferred from a Python type annotation.

    Supports: ``bool``, ``Literal[...]``, ``tuple[str, ...]``, ``str``, and unions/aliases of these.
    """
    flag = f"--{name.replace('_', '-')}"
    for raw_cand in _non_none_args(annotation):
        cand = _resolve_alias(raw_cand)
        if cand is bool:
            parser.add_argument(flag, action="store_true", default=None)
            return
        origin = get_origin(cand)
        if origin is Literal:
            parser.add_argument(flag, choices=list(get_args(cand)), default=None)
            return
        if origin is tuple:
            tuple_args = get_args(cand)
            if tuple_args and tuple_args[0] is str:
                parser.add_argument(flag, action="append", default=None)
                return
        if cand is str:
            parser.add_argument(flag, default=None)
            return
    msg = f"Unsupported CLI annotation for {name!r}: {annotation!r}"
    raise TypeError(msg)


def add_load_args(parser: argparse.ArgumentParser) -> None:
    """Generate CLI flags for ``load()`` parameters listed in ``CLI_LOAD_PARAMS``."""
    hints = get_type_hints(load)
    for name in CLI_LOAD_PARAMS:
        if name not in hints:
            msg = f"{name!r} not found in load() signature"
            raise RuntimeError(msg)
        add_typed_arg(parser, name, hints[name])


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
    """Collect non-``None`` values for ``CLI_LOAD_PARAMS`` from a derived dataclass."""
    return {name: v for name in CLI_LOAD_PARAMS if (v := getattr(args, name, None)) is not None}


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
    hints = get_type_hints(load)
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

    inspect_args = make_dataclass(
        "InspectArgs",
        [
            *common,
            ("field", str | None, field(default=None)),
            ("format", Literal["json", "text"] | None, field(default=None)),
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


def build_sources(specs: list[str]) -> list[Source]:
    """Parse each spec and instantiate the corresponding Source."""
    sources: list[Source] = []
    for spec in specs:
        klass, kwargs = parse_source_spec(spec)
        sources.append(klass(**kwargs))
    return sources
