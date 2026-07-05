import contextlib
import logging
from dataclasses import Field, fields, is_dataclass
from enum import Flag
from typing import Any, cast, get_type_hints

from adaptix import Retort

from dature.errors.location import ErrorContext
from dature.field_path import FieldPath, extract_field_path
from dature.protocols import DataclassInstance
from dature.skip_field_provider import FilterResult, filter_invalid_fields
from dature.sources.protocol import SourceProtocol
from dature.type_aliases import JSONValue, NestedConflicts

logger = logging.getLogger("dature")


def coerce_flag_fields[T](data: JSONValue, schema: type[T]) -> JSONValue:
    if not isinstance(data, dict) or not is_dataclass(schema):
        return data

    type_hints = get_type_hints(schema)
    coerced = dict(data)
    for field in fields(cast("type[DataclassInstance]", schema)):
        hint = type_hints.get(field.name)
        if hint is None:
            continue
        if isinstance(hint, type) and issubclass(hint, Flag):
            value = coerced.get(field.name)
            if isinstance(value, str):
                with contextlib.suppress(ValueError):
                    coerced[field.name] = int(value)
            elif isinstance(value, Flag):
                coerced[field.name] = value.value
    return coerced


def build_error_ctx(
    metadata: SourceProtocol,
    dataclass_name: str,
    *,
    secret_paths: frozenset[str] = frozenset(),
    mask_secrets: bool = False,
    nested_conflicts: NestedConflicts | None = None,
) -> ErrorContext:
    return ErrorContext(
        dataclass_name=dataclass_name,
        source=metadata,
        secret_paths=secret_paths,
        mask_secrets=mask_secrets,
        nested_conflicts=nested_conflicts,
    )


def get_allowed_fields(
    *,
    skip_value: bool | tuple[FieldPath, ...],
    schema: type[DataclassInstance] | None = None,
) -> set[str] | None:
    if skip_value is True:
        return None
    if isinstance(skip_value, tuple):
        return {extract_field_path(field_path, schema) for field_path in skip_value}
    return None


def apply_skip_invalid(
    *,
    raw: JSONValue,
    skip_field_if_invalid: bool | tuple[FieldPath, ...] | None,
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
