import logging
from collections.abc import Callable
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dature.config import config
from dature.errors.exceptions import DatureConfigError
from dature.errors.formatter import enrich_skipped_errors, handle_load_errors
from dature.errors.location import read_file_content
from dature.load_report import FieldOrigin, LoadReport, SourceEntry, attach_load_report
from dature.loading.context import (
    apply_skip_invalid,
    build_error_ctx,
    coerce_flag_fields,
    ensure_retort,
    make_validating_post_init,
    merge_fields,
)
from dature.loading.resolver import resolve_loader_class
from dature.loading.source_loading import SkippedFieldSource
from dature.masking.detection import build_secret_paths
from dature.masking.masking import mask_json_value
from dature.metadata import LoadMetadata
from dature.protocols import DataclassInstance, LoaderProtocol
from dature.types import JSONValue

if TYPE_CHECKING:
    from adaptix import Retort

logger = logging.getLogger("dature")


def _resolve_single_mask_secrets(metadata: LoadMetadata) -> bool:
    if metadata.mask_secrets is not None:
        return metadata.mask_secrets
    return config.masking.mask_secrets


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
    def __init__(
        self,
        *,
        loader_instance: LoaderProtocol,
        file_path: Path,
        cls: type[DataclassInstance],
        metadata: LoadMetadata,
        cache: bool,
        debug: bool,
    ) -> None:
        ensure_retort(loader_instance, cls)
        validating_retort = loader_instance.create_validating_retort(cls)

        self.loader_instance = loader_instance
        self.file_path = file_path
        self.cls = cls
        self.metadata = metadata
        self.cache = cache
        self.debug = debug
        self.cached_data: DataclassInstance | None = None
        self.field_list = fields(cls)
        self.original_init = cls.__init__
        self.original_post_init = getattr(cls, "__post_init__", None)
        self.validation_loader: Callable[[JSONValue], DataclassInstance] = validating_retort.get_loader(cls)
        self.validating = False
        self.loading = False

        loader_class = resolve_loader_class(metadata.loader, metadata.file_)
        self.loader_type = loader_class.display_name

        self.secret_paths: frozenset[str] = frozenset()
        if _resolve_single_mask_secrets(metadata):
            extra_patterns = metadata.secret_field_names or ()
            self.secret_paths = build_secret_paths(cls, extra_patterns=extra_patterns)

        self.error_ctx = build_error_ctx(metadata, cls.__name__, secret_paths=self.secret_paths)

        # probe_retort создаётся заранее, чтобы adaptix увидел оригинальную сигнатуру
        self.probe_retort: Retort | None = None
        if metadata.skip_if_invalid:
            self.probe_retort = loader_instance.create_probe_retort()
            self.probe_retort.get_loader(cls)


def _load_single_source(ctx: _PatchContext) -> DataclassInstance:
    raw_data = handle_load_errors(
        func=lambda: ctx.loader_instance.load_raw(ctx.file_path),
        ctx=ctx.error_ctx,
    )

    filter_result = apply_skip_invalid(
        raw=raw_data,
        skip_if_invalid=ctx.metadata.skip_if_invalid,
        loader_instance=ctx.loader_instance,
        dataclass_=ctx.cls,
        log_prefix=f"[{ctx.cls.__name__}]",
        probe_retort=ctx.probe_retort,
    )
    raw_data = filter_result.cleaned_dict
    raw_data = coerce_flag_fields(raw_data, ctx.cls)

    skipped_fields: dict[str, list[SkippedFieldSource]] = {}
    file_content = read_file_content(ctx.error_ctx.file_path)
    for path in filter_result.skipped_paths:
        skipped_fields.setdefault(path, []).append(
            SkippedFieldSource(metadata=ctx.metadata, error_ctx=ctx.error_ctx, file_content=file_content),
        )

    def _transform(rd: JSONValue = raw_data) -> DataclassInstance:
        return ctx.loader_instance.transform_to_dataclass(rd, ctx.cls)

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
                file_path=str(ctx.file_path),
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
                file_path=str(ctx.file_path) if ctx.metadata.file_ is not None else None,
                raw_data=result_dict,
                secret_paths=ctx.secret_paths,
            )
            attach_load_report(self, report)

        if ctx.original_post_init is None:
            self.__post_init__()  # type: ignore[attr-defined]

    return new_init


def load_as_function(  # noqa: C901
    *,
    loader_instance: LoaderProtocol,
    file_path: Path,
    dataclass_: type[DataclassInstance],
    metadata: LoadMetadata,
    debug: bool,
) -> DataclassInstance:
    loader_class = resolve_loader_class(metadata.loader, metadata.file_)
    display_name = loader_class.display_name

    secret_paths: frozenset[str] = frozenset()
    if metadata.mask_secrets is None or metadata.mask_secrets:
        extra_patterns = metadata.secret_field_names or ()
        secret_paths = build_secret_paths(dataclass_, extra_patterns=extra_patterns)

    error_ctx = build_error_ctx(metadata, dataclass_.__name__, secret_paths=secret_paths)

    raw_data = handle_load_errors(
        func=lambda: loader_instance.load_raw(file_path),
        ctx=error_ctx,
    )

    filter_result = apply_skip_invalid(
        raw=raw_data,
        skip_if_invalid=metadata.skip_if_invalid,
        loader_instance=loader_instance,
        dataclass_=dataclass_,
        log_prefix=f"[{dataclass_.__name__}]",
    )
    raw_data = filter_result.cleaned_dict

    skipped_fields: dict[str, list[SkippedFieldSource]] = {}
    file_content = read_file_content(error_ctx.file_path)
    for path in filter_result.skipped_paths:
        skipped_fields.setdefault(path, []).append(
            SkippedFieldSource(metadata=metadata, error_ctx=error_ctx, file_content=file_content),
        )

    report: LoadReport | None = None
    if debug:
        report = _build_single_source_report(
            dataclass_name=dataclass_.__name__,
            loader_type=display_name,
            file_path=metadata.file_,
            raw_data=raw_data,
            secret_paths=secret_paths,
        )

    _log_single_source_load(
        dataclass_name=dataclass_.__name__,
        loader_type=display_name,
        file_path=str(file_path),
        data=raw_data if isinstance(raw_data, dict) else {},
        secret_paths=secret_paths,
    )

    validating_retort = loader_instance.create_validating_retort(dataclass_)
    validation_loader = validating_retort.get_loader(dataclass_)
    raw_data = coerce_flag_fields(raw_data, dataclass_)

    try:
        handle_load_errors(
            func=lambda: validation_loader(raw_data),
            ctx=error_ctx,
        )
    except DatureConfigError as exc:
        if report is not None:
            attach_load_report(dataclass_, report)
        if skipped_fields:
            raise enrich_skipped_errors(exc, skipped_fields) from exc
        raise

    try:
        result = handle_load_errors(
            func=lambda: loader_instance.transform_to_dataclass(raw_data, dataclass_),
            ctx=error_ctx,
        )
    except DatureConfigError as exc:
        if report is not None:
            attach_load_report(dataclass_, report)
        if skipped_fields:
            raise enrich_skipped_errors(exc, skipped_fields) from exc
        raise

    if report is not None:
        attach_load_report(result, report)

    return result


def make_decorator(
    *,
    loader_instance: LoaderProtocol,
    file_path: Path,
    metadata: LoadMetadata,
    cache: bool,
    debug: bool,
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]:
    def decorator(cls: type[DataclassInstance]) -> type[DataclassInstance]:
        if not is_dataclass(cls):
            msg = f"{cls.__name__} must be a dataclass"
            raise TypeError(msg)

        ctx = _PatchContext(
            loader_instance=loader_instance,
            file_path=file_path,
            cls=cls,
            metadata=metadata,
            cache=cache,
            debug=debug,
        )
        cls.__init__ = _make_new_init(ctx)  # type: ignore[method-assign]
        cls.__post_init__ = make_validating_post_init(ctx)  # type: ignore[attr-defined]
        return cls

    return decorator
