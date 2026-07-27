"""Protocol definitions for source types.

``SourceProtocol`` — the minimal interface that any source must satisfy to be
accepted by the ``Loader``.  It covers only operations that apply to *all*
source types (env, file, CLI, remote, and custom).

``FileSourceProtocol`` — the additional interface for sources that read from a
file on disk.  The loading machinery checks ``isinstance(source, FileSourceProtocol)``
to decide whether to access file-specific attributes (``skip_if_broken``,
``skip_if_missing``, ``file_display``, ``file_path_for_errors``, ``encoding_for_errors``).

All ``SourceProtocol`` implementations must be dataclasses (signalled by
``__dataclass_fields__``), which enables ``dataclasses.fields()`` and
``dataclasses.replace()`` to work uniformly across the loading machinery.
"""

from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from adaptix.provider import Provider

from dature.conditions import Condition
from dature.errors.loc_types import CaretSpan, LineRange, SourceLocation
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


@runtime_checkable
class SourceProtocol(Protocol):
    """Minimal interface required by the ``Loader`` to process any source.

    Implementations must be dataclasses (``__dataclass_fields__`` is required),
    which allows the loading machinery to use ``dataclasses.fields()`` and
    ``dataclasses.replace()`` uniformly.
    """

    __dataclass_fields__: ClassVar[dict[str, Any]]

    format_name: str
    location_label: str
    config_group: str | None

    prefix: DotSeparatedPath | None
    name_style: NameStyle | None
    field_mapping: FieldMapping | None
    validators: FieldValidators | None
    expand_env_vars: ExpandEnvVarsMode | None
    skip_field_if_invalid: SkipFieldsInvalid
    type_loaders: TypeLoaderMap | None
    tag: str | None
    when: Condition | None

    @property
    def resolved_tag(self) -> str: ...

    def load_raw(self) -> LoadRawResult: ...

    def display_name(self) -> str: ...

    def check_invariants(self) -> None: ...

    def format_loaders(self) -> list[Provider]: ...

    def resolve_location(
        self,
        *,
        field_path: list[str],
        nested_conflict: NestedConflict | None,
        input_value: JSONValue,
        loaded_data: JSONValue | None,
    ) -> list[SourceLocation]: ...

    def compute_line_carets(
        self,
        content_lines: list[str],
        *,
        input_value: JSONValue,
        field_key: str | None,
    ) -> list[CaretSpan]: ...


@runtime_checkable
class FileSourceProtocol(Protocol):
    """Additional interface for sources that read from a file on disk.

    The loading machinery checks ``isinstance(source, FileSourceProtocol)`` to
    decide whether to access file-specific attributes.  Any class that exposes
    these five members satisfies the protocol — subclassing ``FileFieldMixin``
    is sufficient but not required.
    """

    skip_if_broken: bool | None
    skip_if_missing: bool | None
    encoding: str | None

    def file_display(self) -> str | None: ...

    def file_path_for_errors(self) -> Path | None: ...

    def build_line_index(self, content: str) -> "dict[tuple[str, ...], LineRange] | None": ...
