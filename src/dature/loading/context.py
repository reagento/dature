import contextlib
import logging
from collections.abc import Callable
from dataclasses import Field, asdict, fields, is_dataclass
from enum import Flag
from pathlib import Path
from typing import Any, Protocol, cast, get_type_hints, runtime_checkable

from adaptix import Retort

from dature.errors.formatter import handle_load_errors
from dature.errors.location import ErrorContext
from dature.field_path import FieldPath
from dature.loading.resolver import resolve_loader_class
from dature.merging.predicate import extract_field_path
from dature.metadata import Source
from dature.protocols import DataclassInstance, LoaderProtocol
from dature.skip_field_provider import FilterResult, filter_invalid_fields
from dature.types import FILE_LIKE_TYPES, JSONValue, NestedConflicts

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
    metadata: Source,
    dataclass_name: str,
    *,
    secret_paths: frozenset[str] = frozenset(),
    mask_secrets: bool = False,
    nested_conflicts: NestedConflicts | None = None,
) -> ErrorContext:
    loader_class = resolve_loader_class(metadata.loader, metadata.file)
    if isinstance(metadata.file, FILE_LIKE_TYPES):
        error_file_path = None
    elif metadata.file is not None:
        error_file_path = Path(metadata.file)
    else:
        error_file_path = None
    return ErrorContext(
        dataclass_name=dataclass_name,
        loader_class=loader_class,
        file_path=error_file_path,
        prefix=metadata.prefix,
        split_symbols=metadata.split_symbols,
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
        return {extract_field_path(fp, schema) for fp in skip_value}
    return None


def apply_skip_invalid(
    *,
    raw: JSONValue,
    skip_if_invalid: bool | tuple[FieldPath, ...] | None,
    loader_instance: LoaderProtocol,
    schema: type[DataclassInstance],
    log_prefix: str,
    probe_retort: Retort | None = None,
) -> FilterResult:
    if not skip_if_invalid:
        return FilterResult(cleaned_dict=raw, skipped_paths=[])

    allowed_fields = get_allowed_fields(skip_value=skip_if_invalid, schema=schema)

    if probe_retort is None:
        probe_retort = loader_instance.create_probe_retort()

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


def ensure_retort(loader_instance: LoaderProtocol, cls: type[DataclassInstance]) -> None:
    """Creates a replacement response to __init__ so that Adaptix sees the original signature."""
    if cls not in loader_instance.retorts:
        loader_instance.retorts[cls] = loader_instance.create_retort()
    loader_instance.retorts[cls].get_loader(cls)


@runtime_checkable
class PatchContext(Protocol):
    loading: bool
    validating: bool
    cls: type[DataclassInstance]
    original_post_init: Callable[..., None] | None
    validation_loader: Callable[[JSONValue], DataclassInstance]
    error_ctx: ErrorContext


def make_validating_post_init(ctx: PatchContext) -> Callable[..., None]:
    def new_post_init(self: DataclassInstance) -> None:
        if ctx.loading:
            return

        if ctx.validating:
            return

        if ctx.original_post_init is not None:
            ctx.original_post_init(self)

        ctx.validating = True
        try:
            obj_dict = coerce_flag_fields(asdict(self), ctx.cls)
            handle_load_errors(
                func=lambda: ctx.validation_loader(obj_dict),
                ctx=ctx.error_ctx,
            )
        finally:
            ctx.validating = False

    return new_post_init
