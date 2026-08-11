import contextlib
import logging
from collections.abc import Sequence
from dataclasses import Field
from enum import Flag
from typing import Any

from adaptix import Retort

from dature.errors.location import ErrorContext
from dature.field_path import F, extract_field_path
from dature.protocols import DataclassInstance
from dature.skip_field_provider import FilterResult, filter_invalid_fields
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import JSONValue, MaskingMode, NestedConflicts, SkipFieldsInvalid

logger = logging.getLogger("dature")


def coerce_flag_fields(data: JSONValue, flag_field_names: frozenset[str]) -> JSONValue:
    """Coerce ``enum.Flag`` field values (str → int, Flag → int) for the named fields.

    *flag_field_names* is precomputed once per schema by ``RetortCache`` so this stays a
    cheap dict walk on the load hot path — no ``get_type_hints`` per call. When the schema
    has no Flag fields the set is empty and *data* is returned unchanged.
    """
    if not flag_field_names or not isinstance(data, dict):
        return data

    coerced = dict(data)
    for name in flag_field_names:
        value = coerced.get(name)
        if isinstance(value, str):
            with contextlib.suppress(ValueError):
                coerced[name] = int(value)
        elif isinstance(value, Flag):
            coerced[name] = value.value
    return coerced


def build_error_ctx(
    metadata: SourceProtocol,
    dataclass_name: str,
    *,
    secret_paths: frozenset[str] = frozenset(),
    masking_mode: MaskingMode = "none",
    nested_conflicts: NestedConflicts | None = None,
) -> ErrorContext:
    return ErrorContext(
        dataclass_name=dataclass_name,
        source=metadata,
        secret_paths=secret_paths,
        masking_mode=masking_mode,
        nested_conflicts=nested_conflicts,
    )


def get_allowed_fields(
    *,
    skip_value: SkipFieldsInvalid,
    schema: type[DataclassInstance] | None = None,
) -> set[str] | None:
    if skip_value is F.ANY:
        return None
    if isinstance(skip_value, Sequence) and not isinstance(skip_value, str):
        return {extract_field_path(field_path, schema) for field_path in skip_value}
    return None


def apply_skip_invalid(
    *,
    raw: JSONValue,
    skip_field_if_invalid: SkipFieldsInvalid,
    schema: type[DataclassInstance],
    log_prefix: str,
    probe_retort: Retort | None = None,
) -> FilterResult:
    if not skip_field_if_invalid or probe_retort is None:
        return FilterResult(cleaned_dict=raw, skipped_paths=[])

    allowed_fields = get_allowed_fields(skip_value=skip_field_if_invalid, schema=schema)
    result = filter_invalid_fields(raw, probe_retort, schema, allowed_fields)
    for path in result.skipped_paths:
        logger.warning(
            "%s Skipped invalid field '%s'",
            log_prefix,
            path,
        )
    return result


def merge_fields(
    loaded_data: DataclassInstance,
    field_list: tuple[Field[Any], ...],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    explicit_fields = set(kwargs.keys())
    for i, _ in enumerate(args):
        if i < len(field_list):
            explicit_fields.add(field_list[i].name)

    complete_kwargs = dict(kwargs)
    for field in field_list:
        if field.name not in explicit_fields:
            complete_kwargs[field.name] = getattr(loaded_data, field.name)

    return complete_kwargs
