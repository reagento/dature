"""The field pass: per-source validator run, error reconciliation, default-field fallback,
and decorator-mode replay.

This module is the loading-time counterpart to ``dature/validators/``:
- ``dature/validators/`` *defines* checks — the ``V`` DSL compiled into adaptix providers.
- This module *runs* those checks against real source data at load time.

Four public entry points:
- ``run_source_field_pass`` — validate one source's raw dict through its field validators.
- ``merge_root_and_field_errors`` — combine root-retort and field-pass errors without double-reporting.
- ``compute_default_fallback_errors`` — validate fields that took their dataclass default (no source).
- ``build_revalidation`` — build the ``(validation_loader, error_ctx)`` pair used by the decorator
  mode so that ``Config(field=bad_value)`` re-validates on direct instantiation.
"""

from collections.abc import Callable
from functools import partial
from typing import Any, cast

from dature.config import ErrorDisplayConfig, MaskingConfig
from dature.errors import DatureConfigError, FieldLoadError
from dature.errors.extraction import handle_load_errors
from dature.errors.location import ErrorContext
from dature.loading.context import build_error_ctx
from dature.loading.merge_runtime import resolve_type_loaders
from dature.loading.retort import RetortCache
from dature.protocols import DataclassInstance
from dature.sources.base import IndexedSource
from dature.type_aliases import JSONValue, TypeLoaderMap


def compute_default_fallback_errors(
    annotated_default_fields: tuple[tuple[str, list[Any]], ...],
    validated_field_names: set[str],
    result: DataclassInstance,
) -> list[FieldLoadError]:
    """Run ``Annotated`` validators for fields no source provided (took their dataclass default).

    *annotated_default_fields* is the schema's ``(field_name, predicates)`` map, precomputed
    once per ``RetortCache`` (pure static reflection).  Fields provided by at least one source
    are already in *validated_field_names* and are skipped — they were validated per-source via
    the field pass; only default-value fields need this fallback.
    """
    return [
        FieldLoadError(
            field_path=[name],
            message=predicate.get_error_message(),
            input_value=cast("JSONValue", getattr(result, name, None)),
        )
        for name, predicates in annotated_default_fields
        if name not in validated_field_names
        for predicate in predicates
        if not predicate.get_validator_func()(getattr(result, name, None))
    ]


def run_source_field_pass[T: DataclassInstance](  # noqa: PLR0913
    *,
    indexed: IndexedSource,
    raw: JSONValue,
    schema: type[T],
    retort_cache: RetortCache,
    resolved_type_loaders: TypeLoaderMap | None,
    error_ctx: ErrorContext,
    loaded_data: JSONValue,
) -> tuple[dict[str, object] | None, list[FieldLoadError]]:
    """Run ``field_pass(skip=False)`` for one source on its own raw dict.

    Returns ``(result_dict, [])`` on success, ``(None, errors)`` on validation failure.
    The caller decides how to handle errors: multi-source raises immediately; single-source
    defers to merge with root-retort errors so both are reported in one ExceptionGroup.
    """
    field_pass_loader = retort_cache.field_pass(
        indexed, skip=False, resolved_type_loaders=resolved_type_loaders
    ).get_loader(schema)
    try:
        field_pass_result = handle_load_errors(
            func=partial(field_pass_loader, raw), ctx=error_ctx, loaded_data=loaded_data
        )
    except DatureConfigError as exc:
        return None, cast("list[FieldLoadError]", list(exc.exceptions))
    return (field_pass_result if isinstance(field_pass_result, dict) else None), []


def merge_root_and_field_errors(
    schema_name: str,
    root_errors: list[FieldLoadError],
    field_errors: list[FieldLoadError],
) -> DatureConfigError:
    """Combine root-retort and field-pass errors; root field-paths take priority.

    Field-pass errors are appended only for paths the root retort did not already report,
    so a coercion/missing-field failure and a validator failure on the same path do not
    double-report.
    """
    root_paths = {tuple(error.field_path) for error in root_errors}
    return DatureConfigError(
        schema_name,
        [*root_errors, *(fe for fe in field_errors if tuple(fe.field_path) not in root_paths)],
    )


# ---------------------------------------------------------------------------
# Decorator-mode replay
# ---------------------------------------------------------------------------


def _make_validation_loader(
    *,
    retort_cache: RetortCache,
    indexed: IndexedSource,
    schema: type[DataclassInstance],
    ctx: ErrorContext,
    resolved_type_loaders: TypeLoaderMap | None,
) -> Callable[[JSONValue], DataclassInstance]:
    """Build the decorator-mode re-validation loader for direct instantiation.

    When the source/schema has field validators, run the field pass (Annotated/source validators)
    and final_retort (type coercion + root validators), merging their errors so field-level
    and schema-level failures surface together. Otherwise return a plain final_retort loader.
    """

    def _load_and_construct(data: JSONValue) -> DataclassInstance:
        return retort_cache.final_retort(indexed, resolved_type_loaders=resolved_type_loaders).load(data, schema)

    if not retort_cache.has_validators(indexed):
        return _load_and_construct

    field_pass_loader = retort_cache.field_pass(
        indexed, skip=False, resolved_type_loaders=resolved_type_loaders
    ).get_loader(schema)
    schema_name = schema.__name__

    def _combined(data: JSONValue) -> DataclassInstance:
        field_pass_errors: list[FieldLoadError] = []
        try:
            handle_load_errors(func=lambda: field_pass_loader(data), ctx=ctx)
        except DatureConfigError as field_pass_error:
            field_pass_errors = cast("list[FieldLoadError]", list(field_pass_error.exceptions))
        try:
            constructed = handle_load_errors(func=lambda: _load_and_construct(data), ctx=ctx)
        except DatureConfigError as root_error:
            raise merge_root_and_field_errors(
                schema_name,
                cast("list[FieldLoadError]", list(root_error.exceptions)),
                field_pass_errors,
            ) from None
        if field_pass_errors:
            raise DatureConfigError(schema_name, field_pass_errors)
        return constructed

    return _combined


def build_revalidation[T: DataclassInstance](  # noqa: PLR0913
    *,
    indexed: IndexedSource,
    schema: type[T],
    retort_cache: RetortCache,
    type_loaders: TypeLoaderMap | None,
    secret_paths: frozenset[str],
    masking: MaskingConfig,
    error_display: ErrorDisplayConfig,
) -> tuple[Callable[[JSONValue], DataclassInstance], ErrorContext]:
    """Build the decorator-mode replay loader and its error context.

    Returns ``(validation_loader, error_ctx)``.  *validation_loader* is stored on ``Loader``
    so that the subclass ``__init__`` can re-validate on direct instantiation (``Config(field=bad)``).
    """
    resolved_type_loaders = resolve_type_loaders(indexed.source, type_loaders)
    ctx = build_error_ctx(
        indexed.source,
        schema.__name__,
        secret_paths=secret_paths,
        masking=masking,
        error_display=error_display,
    )
    validation_loader = _make_validation_loader(
        retort_cache=retort_cache,
        indexed=indexed,
        schema=schema,
        ctx=ctx,
        resolved_type_loaders=resolved_type_loaders,
    )
    return validation_loader, ctx
