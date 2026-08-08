"""Core ``Source`` ABC plus utilities shared across all source types.

Owns the ``Source`` abstract base class, ``string_value_loaders``, and
``clone_source``. File-based, flat-key, and remote subclasses live in
``file_source``, ``flat_key``, and ``remote`` respectively. Caret / line-range
rendering helpers live in ``presentation``.
"""

import abc
import json
import logging
import warnings
from contextlib import suppress
from dataclasses import MISSING, dataclass, fields, replace
from datetime import date, datetime, time
from typing import Any, ClassVar, Final, cast

from adaptix import loader
from adaptix.provider import Provider

from dature._deprecations import REMOVAL_NOTICE, normalize_skip_bool
from dature.coercion import (
    bool_loader,
    bytearray_from_json_string,
    bytearray_from_string,
    bytes_passthrough,
    date_from_string,
    datetime_from_string,
    float_from_string,
    none_from_empty_string,
    optional_from_empty_string,
    str_from_scalar,
    time_from_string,
)
from dature.conditions import Condition
from dature.errors import CaretSpan, LineRange, SourceLocation
from dature.expansion.env_expand import expand_env_vars
from dature.field_path import Absolute, FieldPath
from dature.sources.presentation import (
    compute_line_carets as _compute_line_carets,
)
from dature.sources.presentation import empty_location
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import (
    DotSeparatedPath,
    ExpandEnvVarsMode,
    FieldMapping,
    JSONValue,
    LoadRawResult,
    NameStyle,
    NestedConflict,
    SkipFieldsInvalid,
    TypeLoaderMap,
)
from dature.validators.aliases import FieldValidators
from dature.validators.base import _validate_root_validators
from dature.validators.root import RootPredicate

logger = logging.getLogger("dature")


_STRING_VALUE_LOADERS: Final[tuple[Provider, ...]] = (
    loader(str, str_from_scalar),
    loader(float, float_from_string),
    loader(date, date_from_string),
    loader(datetime, datetime_from_string),
    loader(time, time_from_string),
    loader(bytearray, bytearray_from_json_string),
    loader(type(None), none_from_empty_string),
    loader(str | None, optional_from_empty_string),
    loader(bool, bool_loader),
)


def string_value_loaders() -> list[Provider]:
    return list(_STRING_VALUE_LOADERS)


_BYTES_VALUE_LOADERS: Final[tuple[Provider, ...]] = (loader(bytes, bytes_passthrough),)


def bytes_value_loaders() -> list[Provider]:
    return list(_BYTES_VALUE_LOADERS)


_REMOTE_VALUE_LOADERS: Final[tuple[Provider, ...]] = (
    loader(float, float_from_string),
    loader(bytearray, bytearray_from_string),
)


def remote_value_loaders() -> list[Provider]:
    """Loaders for native-JSON remote responses (Vault, Consul ``decode="json"``).

    ``float`` needs a string loader because JSON has no ``Infinity``/``NaN`` literals, so
    those values arrive as strings (``"inf"``/``"nan"``) even though the rest of the payload
    is natively typed. ``bytearray`` has no JSON representation at all, so it always arrives
    as a plain string.
    """
    return list(_REMOTE_VALUE_LOADERS)


def _set_value_at_path(
    target: "dict[str, JSONValue]",
    parts: "tuple[str, ...]",
    value: "JSONValue",
) -> None:
    """Set *value* at the nested path *parts* inside *target*, only if the leaf is absent."""
    for part in parts[:-1]:
        inner = target.setdefault(part, {})
        if not isinstance(inner, dict):
            return
        target = inner
    if parts[-1] not in target:
        target[parts[-1]] = value


# --8<-- [start:load-metadata]
@dataclass(kw_only=True, repr=False)
class Source(abc.ABC):
    prefix: "DotSeparatedPath | None" = None
    name_style: "NameStyle | None" = None
    field_mapping: "FieldMapping | None" = None
    validators: "FieldValidators | None" = None
    expand_env_vars: "ExpandEnvVarsMode | None" = None
    skip_field_if_invalid: "SkipFieldsInvalid" = None
    type_loaders: "TypeLoaderMap | None" = None
    tag: str | None = None
    when: "Condition | None" = None

    format_name: str = ""
    location_label: str = ""
    config_group: str | None = None

    root_validators: ClassVar[tuple[RootPredicate, ...]] = ()
    """Cross-field / required-ness checks run by ``validate_source`` after config-group
    merge and cross-ref interpolation. Built with ``V.root(...)``, e.g.::

        root_validators: ClassVar[tuple[RootPredicate, ...]] = (
            V.root(lambda s: bool(s.host), error_message="host is required"),
        )

    Not to be confused with the ``root_validators=`` parameter of :func:`dature.load` /
    :class:`~dature.loading.loader.Loader`, which validates the *merged schema instance*
    after loading — this validates the *source* itself, before it is loaded.
    """

    # --8<-- [end:load-metadata]
    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init_subclass__(**kwargs)
        if "check_invariants" in cls.__dict__:
            warnings.warn(
                f"{cls.__name__}.check_invariants() is deprecated and is no longer called; "
                "express invariants declaratively instead — Literal field types, "
                "Annotated[..., V ...] predicates, or root_validators=(V.root(...), ...). "
                f"{REMOVAL_NOTICE}",
                DeprecationWarning,
                stacklevel=2,
            )
        if "root_validators" in cls.__dict__:
            _validate_root_validators(cls.__dict__["root_validators"])

    def __post_init__(self) -> None:
        if self.when is not None and not isinstance(self.when, Condition):
            msg = (
                f"when= must be a Condition built with the When() DSL, "
                f"got {type(self.when).__name__!r}. "
                'Example: when=When("${APP_ENV}") == "prod"'
            )
            raise TypeError(msg)
        self.skip_field_if_invalid = normalize_skip_bool(self.skip_field_if_invalid)

    def __repr__(self) -> str:
        parts = []
        for f in fields(self):
            if not f.init or not f.repr:
                continue
            value = getattr(self, f.name, MISSING)
            if value is MISSING:
                continue
            if f.default is not MISSING and value == f.default:
                continue
            if f.default_factory is not MISSING:
                with suppress(Exception):
                    if value == f.default_factory():
                        continue
            parts.append(f"{f.name}={value!r}")
        return f"{type(self).__name__}({', '.join(parts)})"

    @property
    def resolved_tag(self) -> str:
        """Tag used to identify this source in ${@tag.key} cross-refs.

        Defaults to format_name when tag is not set explicitly.
        """
        return self.tag if self.tag is not None else self.format_name

    def display_name(self) -> str:
        return self.format_name

    def _alias_to_field_name(self, raw_key: str, *, absolute: bool = False) -> str | None:
        """Return the dataclass field name if *raw_key* is a field_mapping alias, else None.

        Args:
            raw_key: The source key to look up (already stripped of prefix for relative
                aliases; the full original key for absolute ones).
            absolute: When *True*, only :class:`~dature.field_path.Absolute` aliases are
                considered (prefix-independent lookup).  When *False* (default), only plain
                string aliases are considered.
        """
        if not self.field_mapping:
            return None
        for field_path, aliases in self.field_mapping.items():
            if not isinstance(field_path, FieldPath):
                continue
            alias_list: tuple[str, ...] = (aliases,) if isinstance(aliases, str) else tuple(aliases)
            for alias in alias_list:
                is_absolute = isinstance(alias, Absolute)
                if is_absolute != absolute:
                    continue
                if alias == raw_key and field_path.parts:
                    return field_path.parts[-1]
        return None

    def _absolute_alias_keys(self) -> frozenset[str]:
        """Return the set of :class:`~dature.field_path.Absolute` alias source keys.

        Absolute aliases bypass the prefix filter and are matched against the full
        source key, so a prefix-based early filter must always let these keys through.
        """
        if not self.field_mapping:
            return frozenset()
        keys: set[str] = set()
        for field_path, aliases in self.field_mapping.items():
            if not isinstance(field_path, FieldPath):
                continue
            alias_list: tuple[str, ...] = (aliases,) if isinstance(aliases, str) else tuple(aliases)
            keys.update(alias for alias in alias_list if isinstance(alias, Absolute))
        return frozenset(keys)

    def format_loaders(self) -> "list[Provider]":
        legacy = getattr(type(self), "additional_loaders", None)
        if legacy is not None:
            warnings.warn(
                f"{type(self).__name__}.additional_loaders() is deprecated; rename it to "
                f"format_loaders(). {REMOVAL_NOTICE}",
                DeprecationWarning,
                stacklevel=2,
            )
            return cast("list[Provider]", legacy(self))
        return []

    @staticmethod
    def _infer_type(value: str) -> JSONValue:
        if value == "":
            return value

        try:
            return cast("JSONValue", json.loads(value))
        except (json.JSONDecodeError, ValueError):
            return value

    @classmethod
    def _parse_string_values(cls, data: JSONValue, *, infer_scalars: bool = False) -> JSONValue:
        if not isinstance(data, dict):
            return data

        result: dict[str, JSONValue] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = cls._parse_string_values(value, infer_scalars=True)
            elif isinstance(value, str) and (infer_scalars or value.startswith(("[", "{"))):
                result[key] = cls._infer_type(value)
            else:
                result[key] = value
        return result

    @abc.abstractmethod
    def _load(self) -> JSONValue: ...

    def _apply_prefix(self, data: JSONValue) -> JSONValue:
        root = data
        if self.prefix:
            for key in self.prefix.split("."):
                if not isinstance(data, dict) or key not in data:
                    return {}
                data = data[key]

        if not self.field_mapping or not isinstance(root, dict) or not isinstance(data, dict):
            return data

        # Inject Absolute alias values from the document root so root-level keys remain
        # accessible even when prefix navigation moved into a subtree.
        absolute_entries = [
            (field_path, aliases)
            for field_path, aliases in self.field_mapping.items()
            if isinstance(field_path, FieldPath)
            and field_path.parts
            and any(isinstance(a, Absolute) for a in ((aliases,) if isinstance(aliases, str) else aliases))
        ]
        if not absolute_entries:
            return data

        result = dict(data)
        for field_path, aliases in absolute_entries:
            alias_list = (aliases,) if isinstance(aliases, str) else aliases
            absolute = next((a for a in alias_list if isinstance(a, Absolute) and a in root), None)
            if absolute is not None:
                _set_value_at_path(result, field_path.parts, root[absolute])
        return result

    def _pre_processing(
        self,
        data: JSONValue,
        *,
        resolved_expand: ExpandEnvVarsMode,
    ) -> JSONValue:
        prefixed = self._apply_prefix(data)
        return expand_env_vars(prefixed, mode=resolved_expand)

    def load_raw(self) -> LoadRawResult:
        data = self._load()
        processed = self._pre_processing(data, resolved_expand=self.expand_env_vars)  # type: ignore[arg-type]
        logger.debug(
            "[%s] load_raw: source=%s, raw_keys=%s, after_preprocessing_keys=%s",
            type(self).__name__,
            self.display_name(),
            sorted(data.keys()) if isinstance(data, dict) else "<non-dict>",
            sorted(processed.keys()) if isinstance(processed, dict) else "<non-dict>",
        )
        return LoadRawResult(data=processed, loaded_data=data)

    def build_line_index(self, content: str) -> "dict[tuple[str, ...], LineRange] | None":  # noqa: ARG002
        """Return a mapping from field-path tuples to line ranges within *content*.

        Part of the error-location protocol: called by the errors layer to resolve
        field positions in file content. Override in FileSource subclasses that support
        line-number error reporting. Return ``None`` to opt out (default).
        """
        return None

    def compute_line_carets(
        self,
        content_lines: list[str],
        *,
        input_value: JSONValue,
        field_key: str | None,
    ) -> "list[CaretSpan]":
        """Compute caret spans for *content_lines* pointing at *input_value*.

        Part of the error-location protocol: called by the errors layer when masking
        is applied to already-extracted line content. The default implementation works
        for most text formats; override for special caret placement logic.
        """
        return _compute_line_carets(content_lines, input_value=input_value, field_key=field_key)

    def resolve_location(
        self,
        *,
        field_path: list[str],  # noqa: ARG002
        nested_conflict: NestedConflict | None,  # noqa: ARG002
        input_value: JSONValue = None,  # noqa: ARG002
        loaded_data: "JSONValue | None" = None,  # noqa: ARG002
    ) -> list[SourceLocation]:
        return [empty_location(self.location_label, None)]


@dataclass(frozen=True, slots=True)
class IndexedSource:
    """A source paired with its stable positional index in the Loader's sources tuple.

    The index is the retort-cache identity: clones of the same logical source
    share an index and thus the pre-warmed retort.
    """

    source: SourceProtocol
    index: int


def clone_source[T: SourceProtocol](source: T, overrides: dict[str, object]) -> T:
    """Return a copy of *source* with *overrides* applied.

    Uses ``dataclasses.replace()`` so ``__post_init__`` runs and ``init=False``
    fields reset to their defaults (e.g. ``_resolved_file_path`` → ``None``).
    """
    return replace(source, **overrides)
