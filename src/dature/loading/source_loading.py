"""Post-load error enrichment and per-source preparation helpers.

``enrich_skipped_errors`` enriches ``Missing required field`` errors with
information about fields that were skipped due to ``skip_field_if_invalid``.
``prepare_loaded_source`` is the shared deterministic tail of per-source
pre-processing: error_ctx rebuild on nested_conflicts, file_content read,
and ``apply_skip_invalid`` — called by both ``_do_load_single`` and
``LoadCtx.load``. Per-source helpers that need ``MergeConfig``
(``resolve_type_loaders``, ``should_skip_broken``, ``should_skip_missing``, ``resolve_skip_invalid``)
live in ``dature.loading.merge_runtime`` to avoid import cycles.
"""

from dataclasses import dataclass

from adaptix import Retort

from dature.errors.exceptions import DatureConfigError, DatureError, FieldLoadError
from dature.errors.location import (
    ErrorContext,
    SkippedFieldSource,
    read_file_content,
    resolve_source_location,
)
from dature.field_path import FieldPath
from dature.loading.context import apply_skip_invalid, build_error_ctx
from dature.protocols import DataclassInstance
from dature.sources.protocol import FileSourceProtocol, SourceProtocol
from dature.type_aliases import JSONValue, LoadRawResult


@dataclass(frozen=True, slots=True)
class PreparedSource:
    """Result of the shared per-source pre-processing tail."""

    raw_data: JSONValue
    error_ctx: ErrorContext
    file_content: str | None
    loaded_data: JSONValue
    skipped: "list[tuple[str, SkippedFieldSource]]"


def prepare_loaded_source(  # noqa: PLR0913
    *,
    load_result: LoadRawResult,
    source: SourceProtocol,
    schema: "type[DataclassInstance]",
    dataclass_name: str,
    base_error_ctx: ErrorContext,
    skip_value: "bool | tuple[FieldPath, ...] | None",
    secret_paths: frozenset[str],
    mask_secrets: bool,
    log_prefix: str,
    probe_retort: Retort | None,
) -> PreparedSource:
    """Shared deterministic pre-processing tail for single and multi-source loads.

    Handles: nested_conflicts error_ctx rebuild, file_content read,
    skip_field_if_invalid filtering, and SkippedFieldSource accumulation.
    Broken-source handling, caching, and LoadReport building stay at call sites.
    """
    raw = load_result.data
    loaded_data = load_result.loaded_data
    error_ctx = base_error_ctx
    if load_result.nested_conflicts:
        error_ctx = build_error_ctx(
            source,
            dataclass_name,
            secret_paths=secret_paths,
            mask_secrets=mask_secrets,
            nested_conflicts=load_result.nested_conflicts,
        )
    if isinstance(source, FileSourceProtocol):
        file_content = read_file_content(source.file_path_for_errors(), source.encoding)
    else:
        file_content = None
    filter_result = apply_skip_invalid(
        raw=raw,
        skip_field_if_invalid=skip_value,
        schema=schema,
        log_prefix=log_prefix,
        probe_retort=probe_retort,
    )
    skipped = [
        (
            path,
            SkippedFieldSource(source=source, error_ctx=error_ctx, file_content=file_content, loaded_data=loaded_data),
        )
        for path in filter_result.skipped_paths
    ]
    return PreparedSource(
        raw_data=filter_result.cleaned_dict,
        error_ctx=error_ctx,
        file_content=file_content,
        loaded_data=loaded_data,
        skipped=skipped,
    )


def enrich_skipped_errors(
    err: DatureConfigError,
    skipped_fields: dict[str, list[SkippedFieldSource]],
) -> DatureConfigError:
    updated: list[DatureError] = []
    for exc in err.exceptions:
        if not isinstance(exc, FieldLoadError):
            if isinstance(exc, DatureError):
                updated.append(exc)
            continue

        if exc.message != "Missing required field":
            updated.append(exc)
            continue

        field_name = exc.field_path[-1] if exc.field_path else ""
        sources = skipped_fields.get(field_name)
        if sources is None:
            updated.append(exc)
            continue

        source_reprs = ", ".join(repr(s.source) for s in sources)
        locations = [
            loc
            for s in sources
            for loc in resolve_source_location(
                exc.field_path, s.error_ctx, s.file_content, input_value=exc.input_value, loaded_data=s.loaded_data
            )
        ]
        updated.append(
            FieldLoadError(
                field_path=exc.field_path,
                message=f"Missing required field (invalid in: {source_reprs})",
                input_value=exc.input_value,
                locations=locations,
            ),
        )
    return DatureConfigError(err.dataclass_name, updated)
