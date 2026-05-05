import logging
from collections.abc import Callable
from dataclasses import asdict, fields, is_dataclass
from typing import TYPE_CHECKING, Any

from dature.errors import DatureConfigError
from dature.errors.formatter import enrich_skipped_errors, handle_load_errors
from dature.errors.location import read_file_content
from dature.load_report import FieldOrigin, LoadReport, SourceEntry, attach_load_report
from dature.loading.common import resolve_mask_secrets
from dature.loading.context import (
    apply_skip_invalid,
    build_error_ctx,
    coerce_flag_fields,
    make_validating_post_init,
    merge_fields,
)
from dature.loading.merge_config import SourceParams, apply_source_init_params
from dature.loading.source_loading import (
    SkippedFieldSource,
    resolve_type_loaders,
)
from dature.masking.detection import build_secret_paths
from dature.masking.masking import mask_json_value
from dature.protocols import DataclassInstance
from dature.sources.base import Source
from dature.sources.retort import (
    create_probe_retort,
    create_validating_retort,
    ensure_retort,
    transform_to_dataclass,
)
from dature.types import JSONValue

if TYPE_CHECKING:
    from adaptix import Retort

    from dature.types import TypeLoaderMap

logger = logging.getLogger("dature")


def _log_single_source_load(
    *,
    dataclass_name: str,
    loader_type: str,
    file_path: str,
    data: JSONValue,
    secret_paths: frozenset[str] = frozenset(),
) -> None:
    logger.debug(
        "[%s] Single-source load: loader=%s, file=%s",
        dataclass_name,
        loader_type,
        file_path,
    )
    if secret_paths:
        masked_data = mask_json_value(data, secret_paths=secret_paths)
    else:
        masked_data = data
    logger.debug(
        "[%s] Loaded data: %s",
        dataclass_name,
        masked_data,
    )


def _build_single_source_report(
    *,
    dataclass_name: str,
    loader_type: str,
    file_path: str | None,
    raw_data: JSONValue,
    secret_paths: frozenset[str] = frozenset(),
) -> LoadReport:
    if secret_paths:
        raw_data = mask_json_value(raw_data, secret_paths=secret_paths)

    source = SourceEntry(
        index=0,
        file_path=file_path,
        loader_type=loader_type,
        raw_data=raw_data,
    )

    origins: list[FieldOrigin] = []
    if isinstance(raw_data, dict):
        for key, value in sorted(raw_data.items()):
            origins.append(
                FieldOrigin(
                    key=key,
                    value=value,
                    source_index=0,
                    source_file=file_path,
                    source_loader_type=loader_type,
                ),
            )

    return LoadReport(
        dataclass_name=dataclass_name,
        strategy=None,
        sources=(source,),
        field_origins=tuple(origins),
        merged_data=raw_data,
    )


class _PatchContext:
    def __init__(  # noqa: PLR0913
        self,
        *,
        source: Source,
        cls: type[DataclassInstance],
        cache: bool,
        debug: bool,
        secret_field_names: tuple[str, ...] | None = None,
        mask_secrets: bool | None = None,
        type_loaders: "TypeLoaderMap | None" = None,
    ) -> None:
        self.type_loaders = type_loaders
        ensure_retort(source, cls, resolved_type_loaders=self.type_loaders)
        validating_retort = create_validating_retort(
            source,
            cls,
            resolved_type_loaders=self.type_loaders,
        )

        self.source = source
        self.cls = cls
        self.cache = cache
        self.debug = debug
        self.cached_data: DataclassInstance | None = None
        self.field_list = fields(cls)
        self.original_init = cls.__init__
        self.original_post_init = getattr(cls, "__post_init__", None)
        self.validation_loader: Callable[[JSONValue], DataclassInstance] = validating_retort.get_loader(cls)
        self.validating = False
        self.loading = False

        self.loader_type = source.format_name

        resolved_mask_secrets = resolve_mask_secrets(load_level=mask_secrets)
        self.secret_paths: frozenset[str] = frozenset()
        if resolved_mask_secrets:
            extra_patterns = secret_field_names or ()
            self.secret_paths = build_secret_paths(cls, extra_patterns=extra_patterns)

        self.error_ctx = build_error_ctx(
            source,
            cls.__name__,
            secret_paths=self.secret_paths,
            mask_secrets=resolved_mask_secrets,
        )

        # probe_retort is created early so adaptix sees the original signature
        self.probe_retort: Retort | None = None
        if source.skip_field_if_invalid:
            self.probe_retort = create_probe_retort(source, resolved_type_loaders=self.type_loaders)
            self.probe_retort.get_loader(cls)


def _load_single_source(ctx: _PatchContext) -> DataclassInstance:
    load_result = handle_load_errors(
        func=ctx.source.load_raw,
        ctx=ctx.error_ctx,
    )
    raw_data = load_result.data

    if load_result.nested_conflicts:
        ctx.error_ctx = build_error_ctx(
            ctx.source,
            ctx.cls.__name__,
            secret_paths=ctx.secret_paths,
            mask_secrets=ctx.error_ctx.mask_secrets,
            nested_conflicts=load_result.nested_conflicts,
        )

    filter_result = apply_skip_invalid(
        raw=raw_data,
        skip_field_if_invalid=ctx.source.skip_field_if_invalid,
        source=ctx.source,
        schema=ctx.cls,
        log_prefix=f"[{ctx.cls.__name__}]",
        probe_retort=ctx.probe_retort,
    )
    raw_data = filter_result.cleaned_dict
    raw_data = coerce_flag_fields(raw_data, ctx.cls)

    skipped_fields: dict[str, list[SkippedFieldSource]] = {}
    file_content = read_file_content(ctx.error_ctx.source.file_path_for_errors())
    for path in filter_result.skipped_paths:
        skipped_fields.setdefault(path, []).append(
            SkippedFieldSource(source=ctx.source, error_ctx=ctx.error_ctx, file_content=file_content),
        )

    def _transform(data: JSONValue = raw_data) -> DataclassInstance:
        return transform_to_dataclass(ctx.source, data, ctx.cls, resolved_type_loaders=ctx.type_loaders)

    try:
        loaded_data = handle_load_errors(
            func=_transform,
            ctx=ctx.error_ctx,
        )
    except DatureConfigError as exc:
        if skipped_fields:
            raise enrich_skipped_errors(exc, skipped_fields) from exc
        raise

    return loaded_data


def _make_new_init(ctx: _PatchContext) -> Callable[..., None]:
    def new_init(self: DataclassInstance, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        if ctx.loading:
            ctx.original_init(self, *args, **kwargs)
            return

        if ctx.cache and ctx.cached_data is not None:
            loaded_data = ctx.cached_data
        else:
            ctx.loading = True
            try:
                loaded_data = _load_single_source(ctx)
            finally:
                ctx.loading = False

            _log_single_source_load(
                dataclass_name=ctx.cls.__name__,
                loader_type=ctx.loader_type,
                file_path=ctx.source.display_name(),
                data=asdict(loaded_data),
                secret_paths=ctx.secret_paths,
            )

            if ctx.cache:
                ctx.cached_data = loaded_data

        complete_kwargs = merge_fields(loaded_data, ctx.field_list, args, kwargs)
        ctx.original_init(self, *args, **complete_kwargs)

        if ctx.debug:
            result_dict = asdict(self)
            report = _build_single_source_report(
                dataclass_name=ctx.cls.__name__,
                loader_type=ctx.loader_type,
                file_path=str(path) if (path := ctx.source.file_path_for_errors()) else ctx.source.display_name(),
                raw_data=result_dict,
                secret_paths=ctx.secret_paths,
            )
            attach_load_report(self, report)

        if ctx.original_post_init is None:
            self.__post_init__()  # type: ignore[attr-defined]

    return new_init


def load_as_function(  # noqa: C901, PLR0913
    *,
    source: Source,
    schema: type[DataclassInstance],
    debug: bool,
    secret_field_names: tuple[str, ...] | None = None,
    mask_secrets: bool | None = None,
    source_params: SourceParams | None = None,
    type_loaders: "TypeLoaderMap | None" = None,
) -> DataclassInstance:
    source = apply_source_init_params(source, source_params or SourceParams())
    resolved_type_loaders = resolve_type_loaders(source, type_loaders)
    format_name = source.format_name

    secret_paths: frozenset[str] = frozenset()
    resolved_mask_secrets = resolve_mask_secrets(load_level=mask_secrets)
    if resolved_mask_secrets:
        extra_patterns = secret_field_names or ()
        secret_paths = build_secret_paths(schema, extra_patterns=extra_patterns)
    error_ctx = build_error_ctx(
        source,
        schema.__name__,
        secret_paths=secret_paths,
        mask_secrets=resolved_mask_secrets,
    )

    # Build the validating retort before reading raw data so that V-predicate
    # type-compatibility errors (ValidatorTypeError) surface before any file I/O.
    validating_retort = create_validating_retort(
        source,
        schema,
        resolved_type_loaders=resolved_type_loaders,
    )

    load_result = handle_load_errors(
        func=source.load_raw,
        ctx=error_ctx,
    )
    raw_data = load_result.data

    if load_result.nested_conflicts:
        error_ctx = build_error_ctx(
            source,
            schema.__name__,
            secret_paths=secret_paths,
            mask_secrets=resolved_mask_secrets,
            nested_conflicts=load_result.nested_conflicts,
        )

    filter_result = apply_skip_invalid(
        raw=raw_data,
        skip_field_if_invalid=source.skip_field_if_invalid,
        source=source,
        schema=schema,
        log_prefix=f"[{schema.__name__}]",
    )
    raw_data = filter_result.cleaned_dict

    skipped_fields: dict[str, list[SkippedFieldSource]] = {}
    file_content = read_file_content(error_ctx.source.file_path_for_errors())
    for path in filter_result.skipped_paths:
        skipped_fields.setdefault(path, []).append(
            SkippedFieldSource(source=source, error_ctx=error_ctx, file_content=file_content),
        )

    report: LoadReport | None = None
    if debug:
        source_path = source.file_path_for_errors()
        report_file_path = str(source_path) if source_path is not None else source.display_name()
        report = _build_single_source_report(
            dataclass_name=schema.__name__,
            loader_type=format_name,
            file_path=report_file_path,
            raw_data=raw_data,
            secret_paths=secret_paths,
        )

    _log_single_source_load(
        dataclass_name=schema.__name__,
        loader_type=format_name,
        file_path=source.display_name(),
        data=raw_data if isinstance(raw_data, dict) else {},
        secret_paths=secret_paths,
    )

    validation_loader = validating_retort.get_loader(schema)
    raw_data = coerce_flag_fields(raw_data, schema)

    try:
        handle_load_errors(
            func=lambda: validation_loader(raw_data),
            ctx=error_ctx,
        )
    except DatureConfigError as exc:
        if report is not None:
            attach_load_report(schema, report)
        if skipped_fields:
            raise enrich_skipped_errors(exc, skipped_fields) from exc
        raise

    try:
        result = handle_load_errors(
            func=lambda: transform_to_dataclass(
                source,
                raw_data,
                schema,
                resolved_type_loaders=resolved_type_loaders,
            ),
            ctx=error_ctx,
        )
    except DatureConfigError as exc:
        if report is not None:
            attach_load_report(schema, report)
        if skipped_fields:
            raise enrich_skipped_errors(exc, skipped_fields) from exc
        raise

    if report is not None:
        attach_load_report(result, report)

    return result


def make_decorator(  # noqa: PLR0913
    *,
    source: Source,
    cache: bool,
    debug: bool,
    secret_field_names: tuple[str, ...] | None = None,
    mask_secrets: bool | None = None,
    source_params: SourceParams | None = None,
    type_loaders: "TypeLoaderMap | None" = None,
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]:
    source = apply_source_init_params(source, source_params or SourceParams())
    resolved_type_loaders = resolve_type_loaders(source, type_loaders)

    def decorator(cls: type[DataclassInstance]) -> type[DataclassInstance]:
        if not is_dataclass(cls):
            msg = f"{cls.__name__} must be a dataclass"
            raise TypeError(msg)

        ctx = _PatchContext(
            source=source,
            cls=cls,
            cache=cache,
            debug=debug,
            secret_field_names=secret_field_names,
            mask_secrets=mask_secrets,
            type_loaders=resolved_type_loaders,
        )
        cls.__init__ = _make_new_init(ctx)  # type: ignore[method-assign]
        cls.__post_init__ = make_validating_post_init(ctx)  # type: ignore[attr-defined]
        return cls

    return decorator
