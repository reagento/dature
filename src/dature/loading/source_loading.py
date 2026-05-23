"""Post-load error enrichment for ``LoadCtx`` and the loader.

``enrich_skipped_errors`` enriches ``Missing required field`` errors with
information about fields that were skipped due to ``skip_field_if_invalid``.
Per-source loading helpers (``resolve_type_loaders``, ``should_skip_broken``,
``resolve_skip_invalid``, ``apply_merge_skip_invalid``) live in
``dature.loading.merge_runtime`` together with ``MergeConfig``.
"""

from dature.errors.exceptions import DatureConfigError, DatureError, FieldLoadError
from dature.errors.location import SkippedFieldSource, resolve_source_location


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
            for loc in resolve_source_location(exc.field_path, s.error_ctx, s.file_content, input_value=exc.input_value)
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
