"""Core ``Source`` ABC plus utilities shared across all source types.

Owns the ``Source`` abstract base class, ``string_value_loaders``, and
``clone_source``. File-based, flat-key, and remote subclasses live in
``file_source``, ``flat_key``, and ``remote`` respectively. Caret / line-range
rendering helpers live in ``presentation``.
"""

import abc
import json
import logging
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import MISSING, dataclass, fields, replace
from datetime import date, datetime, time
from typing import Any, ClassVar, Final, cast

from adaptix import loader
from adaptix.provider import Provider

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
from dature.sources.protocol import CascadeAwareProtocol, SourceProtocol
from dature.type_aliases import (
    DotSeparatedPath,
    ExpandEnvVarsMode,
    FieldMapping,
    JSONValue,
    LoadRawResult,
    NameStyle,
    NestedConflict,
    SkipFieldsInvalid,
    StrictMode,
    TypeLoaderMap,
)
from dature.validators.aliases import FieldValidators
from dature.validators.base import validate_root_validators
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
    strict: "StrictMode | None" = None

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
        if "root_validators" in cls.__dict__:
            validate_root_validators(cls.__dict__["root_validators"])

    def __post_init__(self) -> None:
        self._cascaded: frozenset[str] = frozenset()
        self._cross_ref_secrets: tuple[tuple[str, str], ...] = ()
        if self.when is not None and not isinstance(self.when, Condition):
            msg = (
                f"when= must be a Condition built with the When() DSL, "
                f"got {type(self.when).__name__!r}. "
                'Example: when=When("${APP_ENV}") == "prod"'
            )
            raise TypeError(msg)

    @property
    def cascaded_fields(self) -> frozenset[str]:
        """Field names filled by the load/config cascade rather than set by the caller.

        ``__repr__`` hides these, so a source's repr shows only what the caller wrote.
        See :class:`~dature.sources.protocol.CascadeAwareProtocol`.
        """
        return self._cascaded

    def mark_cascaded(self, names: "Iterable[str]") -> None:
        """Record *names* as filled by the load/config cascade, not set by the caller."""
        self._cascaded |= frozenset(names)

    def inherit_cascaded(self, other: object) -> None:
        """Carry cascade provenance over from *other*.

        ``dataclasses.replace()`` (used by :func:`clone_source`) reruns ``__post_init__``,
        which resets ``_cascaded`` — so a clone must re-inherit its source's provenance
        explicitly. *other* is checked structurally rather than via ``isinstance(other,
        Source)``, since custom sources need not subclass ``Source``.
        """
        if isinstance(other, CascadeAwareProtocol):
            self.mark_cascaded(other.cascaded_fields)

    def mark_cross_ref_secrets(self, secrets: "Iterable[tuple[str, str]]") -> None:
        """Record ``(raw, masked)`` pairs substituted into this source from a secret-looking
        cross-source reference (e.g. ``${@vault.db_password}``).

        The raw substituted value is still needed to actually do the source's job (e.g. open
        a file), but display surfaces (repr, debug reports, error messages) must show the
        masked form instead — see :meth:`redact`.
        """
        merged = {**dict(self._cross_ref_secrets), **dict(secrets)}
        self._cross_ref_secrets = tuple(sorted(merged.items(), key=lambda pair: len(pair[0]), reverse=True))

    def redact(self, text: str) -> str:
        """Replace any secret substring recorded by :meth:`mark_cross_ref_secrets` in *text*.

        Longer secrets are replaced first so that one secret's value being a substring of
        another's doesn't leave a partial match. Call once at a display boundary (repr,
        debug report, error message) — not on the value actually used to do the source's job.
        """
        for raw, masked in self._cross_ref_secrets:
            text = text.replace(raw, masked)
        return text

    def __repr__(self) -> str:
        parts = []
        for f in fields(self):
            if not f.init or not f.repr or f.name in self._cascaded:
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
            rendered = self.redact(repr(value)) if isinstance(value, str) else repr(value)
            parts.append(f"{f.name}={rendered}")
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

    def on_prepared(self) -> None:  # noqa: B027
        """Called once per source after load-level/config-group params are injected.

        Runs before ``load_raw()``, once ``self.strict`` (and every other
        ``SourceParams``-cascaded field) has its final, resolved value. No-op by default —
        override to warn about configurations that make a source unreliable for some
        feature (e.g. ``EnvSource`` warns when strict mode is on without a ``prefix``).
        """

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
    fields reset to their defaults (e.g. ``_resolved_file_path`` → ``None``). This also
    resets any cascade provenance the source tracked (see ``CascadeAwareProtocol``), so
    the clone re-inherits it from *source* before it's lost.
    """
    cloned = replace(source, **overrides)
    if isinstance(cloned, CascadeAwareProtocol):
        cloned.inherit_cascaded(source)
    return cloned


def mark_source_cascaded(source: SourceProtocol, names: Iterable[str]) -> None:
    """Record *names* on *source* as cascade-filled; no-op if it isn't cascade-aware."""
    if isinstance(source, CascadeAwareProtocol):
        source.mark_cascaded(names)
