import logging
from collections.abc import Callable
from dataclasses import dataclass as stdlib_dataclass
from dataclasses import fields, is_dataclass
from typing import Any

from dature.errors import DatureConfigError
from dature.errors.formatter import enrich_skipped_errors, handle_load_errors
from dature.load_report import (
    FieldOrigin,
    LoadReport,
    SourceEntry,
    attach_load_report,
    compute_field_origins,
    get_load_report,
)
from dature.loading.common import resolve_mask_secrets
from dature.loading.context import (
    build_error_ctx,
    coerce_flag_fields,
    make_validating_post_init,
    merge_fields,
)
from dature.loading.merge_config import MergeConfig
from dature.loading.source_loading import ResolvedSourceParams, load_sources, resolve_source_params
from dature.masking.detection import build_secret_paths
from dature.masking.masking import mask_field_origins, mask_json_value, mask_source_entries, mask_value
from dature.merging.deep_merge import deep_merge, deep_merge_last_wins, raise_on_conflict
from dature.merging.field_group import FieldGroupContext, validate_field_groups
from dature.merging.predicate import ResolvedFieldGroup, build_field_group_paths, build_field_merge_map
from dature.merging.strategy import FieldMergeStrategyEnum, MergeStrategyEnum
from dature.protocols import DataclassInstance
from dature.sources.base import Source
from dature.sources.retort import (
    create_validating_retort,
    ensure_retort,
    transform_to_dataclass,
)
from dature.types import FieldMergeCallable, JSONValue

logger = logging.getLogger("dature")


def _collect_extra_secret_patterns(merge_meta: MergeConfig) -> tuple[str, ...]:
    merge_names = merge_meta.secret_field_names or ()
    source_names: list[str] = []
    for source_item in merge_meta.sources:
        if source_item.secret_field_names is not None:
            source_names.extend(source_item.secret_field_names)
    return merge_names + tuple(source_names)


def _log_merge_step(  # noqa: PLR0913
    *,
    dataclass_name: str,
    step_idx: int,
    strategy: MergeStrategyEnum,
    before: JSONValue,
    source_data: JSONValue,
    after: JSONValue,
    secret_paths: frozenset[str] = frozenset(),
) -> None:
    if isinstance(before, dict) and isinstance(source_data, dict) and isinstance(after, dict):
        added_keys = set(source_data.keys()) - set(before.keys())
        overwritten_keys = set(source_data.keys()) & set(before.keys())
        logger.debug(
            "[%s] Merge step %d (strategy=%s): added=%s, overwritten=%s",
            dataclass_name,
            step_idx,
            strategy,
            sorted(added_keys),
            sorted(overwritten_keys),
        )
    if secret_paths:
        masked_after = mask_json_value(after, secret_paths=secret_paths)
    else:
        masked_after = after
    logger.debug(
        "[%s] State after step %d: %s",
        dataclass_name,
        step_idx,
        masked_after,
    )


def _log_field_origins(
    *,
    dataclass_name: str,
    field_origins: tuple[FieldOrigin, ...],
    secret_paths: frozenset[str] = frozenset(),
) -> None:
    for origin in field_origins:
        if origin.key in secret_paths:
            masked = mask_value(str(origin.value))
            logger.debug(
                "[%s] Field '%s' = %r  <-- source %d (%s)",
                dataclass_name,
                origin.key,
                masked,
                origin.source_index,
                origin.source_file or "<env>",
            )
        else:
            logger.debug(
                "[%s] Field '%s' = %r  <-- source %d (%s)",
                dataclass_name,
                origin.key,
                origin.value,
                origin.source_index,
                origin.source_file or "<env>",
            )


def _build_merge_report(
    *,
    dataclass_name: str,
    strategy: MergeStrategyEnum,
    source_entries: tuple[SourceEntry, ...],
    field_origins: tuple[FieldOrigin, ...],
    merged_data: JSONValue,
    secret_paths: frozenset[str] = frozenset(),
) -> LoadReport:
    if secret_paths:
        source_entries = mask_source_entries(source_entries, secret_paths=secret_paths)
        field_origins = mask_field_origins(field_origins, secret_paths=secret_paths)
        merged_data = mask_json_value(merged_data, secret_paths=secret_paths)

    return LoadReport(
        dataclass_name=dataclass_name,
        strategy=strategy,
        sources=source_entries,
        field_origins=field_origins,
        merged_data=merged_data,
    )


def _collect_leaf_paths(data: JSONValue, prefix: str = "") -> list[str]:
    if not isinstance(data, dict):
        return [prefix] if prefix else []
    paths: list[str] = []
    for key, value in data.items():
        child_path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            paths.extend(_collect_leaf_paths(value, child_path))
        else:
            paths.append(child_path)
    return paths


def _validate_all_field_groups(
    *,
    raw_dicts: list[JSONValue],
    field_group_paths: tuple[ResolvedFieldGroup, ...],
    dataclass_name: str,
    source_reprs: tuple[str, ...],
) -> None:
    merged: JSONValue = {}
    field_origins: dict[str, int] = {}
    ctx = FieldGroupContext(
        source_reprs=source_reprs,
        field_origins=field_origins,
        dataclass_name=dataclass_name,
    )
    for step_idx, raw in enumerate(raw_dicts):
        validate_field_groups(
            base=merged,
            source=raw,
            field_group_paths=field_group_paths,
            source_index=step_idx,
            ctx=ctx,
        )
        for leaf_path in _collect_leaf_paths(raw):
            field_origins[leaf_path] = step_idx
        merged = deep_merge_last_wins(merged, raw, field_merge_map=None)


def _collect_field_values(
    raw_dicts: list[JSONValue],
    field_path: str,
) -> list[JSONValue]:
    parts = field_path.split(".")
    values: list[JSONValue] = []
    for raw in raw_dicts:
        current: JSONValue = raw
        found = True
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                found = False
                break
            current = current[part]
        if found:
            values.append(current)
    return values


def _set_nested_value(
    data: JSONValue,
    field_path: str,
    value: JSONValue,
) -> JSONValue:
    if not isinstance(data, dict):
        return data
    parts = field_path.split(".")
    if len(parts) == 1:
        result = dict(data)
        result[parts[0]] = value
        return result
    key = parts[0]
    rest = ".".join(parts[1:])
    result = dict(data)
    if key in result:
        result[key] = _set_nested_value(result[key], rest, value)
    return result


def _merge_raw_dicts(
    *,
    raw_dicts: list[JSONValue],
    strategy: MergeStrategyEnum,
    dataclass_name: str,
    field_merge_map: dict[str, FieldMergeStrategyEnum] | None = None,
    callable_merge_map: dict[str, FieldMergeCallable] | None = None,
    secret_paths: frozenset[str] = frozenset(),
) -> JSONValue:
    merged: JSONValue = {}
    for step_idx, raw in enumerate(raw_dicts):
        before = merged

        if strategy == MergeStrategyEnum.RAISE_ON_CONFLICT:
            merged = deep_merge_last_wins(merged, raw, field_merge_map=field_merge_map)
        else:
            merged = deep_merge(merged, raw, strategy=strategy, field_merge_map=field_merge_map)

        _log_merge_step(
            dataclass_name=dataclass_name,
            step_idx=step_idx,
            strategy=strategy,
            before=before,
            source_data=raw,
            after=merged,
            secret_paths=secret_paths,
        )

    if callable_merge_map:
        for field_path, merge_fn in callable_merge_map.items():
            values = _collect_field_values(raw_dicts, field_path)
            if not values:
                continue
            aggregated = merge_fn(values)
            merged = _set_nested_value(merged, field_path, aggregated)

    return merged


@stdlib_dataclass(frozen=True, slots=True)
class _MergedData[T: DataclassInstance]:
    result: T
    merged_raw: JSONValue
    last_source: Source
    last_resolved: ResolvedSourceParams


def _load_and_merge[T: DataclassInstance](  # noqa: C901
    *,
    merge_meta: MergeConfig,
    schema: type[T],
    debug: bool = False,
) -> _MergedData[T]:
    secret_paths: frozenset[str] = frozenset()
    if resolve_mask_secrets(load_level=merge_meta.mask_secrets):
        extra_patterns = _collect_extra_secret_patterns(merge_meta)
        secret_paths = build_secret_paths(schema, extra_patterns=extra_patterns)

    loaded = load_sources(
        merge_meta=merge_meta,
        dataclass_name=schema.__name__,
        schema=schema,
        secret_paths=secret_paths,
        mask_secrets=resolve_mask_secrets(load_level=merge_meta.mask_secrets),
    )

    merge_maps = build_field_merge_map(merge_meta.field_merges, schema)

    field_group_paths: tuple[ResolvedFieldGroup, ...] = ()
    if merge_meta.field_groups:
        field_group_paths = build_field_group_paths(merge_meta.field_groups, schema)

    if field_group_paths:
        source_reprs = tuple(repr(merge_meta.sources[entry.index]) for entry in loaded.source_entries)
        _validate_all_field_groups(
            raw_dicts=loaded.raw_dicts,
            field_group_paths=field_group_paths,
            dataclass_name=schema.__name__,
            source_reprs=source_reprs,
        )

    if merge_meta.strategy == MergeStrategyEnum.RAISE_ON_CONFLICT:
        raise_on_conflict(
            loaded.raw_dicts,
            loaded.source_ctxs,
            schema.__name__,
            field_merge_map=merge_maps.enum_map or None,
            callable_merge_paths=merge_maps.callable_paths or None,
        )

    merged = _merge_raw_dicts(
        raw_dicts=loaded.raw_dicts,
        strategy=merge_meta.strategy,
        dataclass_name=schema.__name__,
        field_merge_map=merge_maps.enum_map or None,
        callable_merge_map=merge_maps.callable_map or None,
        secret_paths=secret_paths,
    )

    if secret_paths:
        masked_merged = mask_json_value(merged, secret_paths=secret_paths)
    else:
        masked_merged = merged
    logger.debug(
        "[%s] Merged result (strategy=%s, %d sources): %s",
        schema.__name__,
        merge_meta.strategy,
        len(loaded.raw_dicts),
        masked_merged,
    )

    frozen_entries = tuple(loaded.source_entries)
    field_origins = compute_field_origins(
        raw_dicts=loaded.raw_dicts,
        source_entries=frozen_entries,
        strategy=merge_meta.strategy,
    )

    _log_field_origins(
        dataclass_name=schema.__name__,
        field_origins=field_origins,
        secret_paths=secret_paths,
    )

    report: LoadReport | None = None
    if debug:
        report = _build_merge_report(
            dataclass_name=schema.__name__,
            strategy=merge_meta.strategy,
            source_entries=frozen_entries,
            field_origins=field_origins,
            merged_data=merged,
            secret_paths=secret_paths,
        )

    last_resolved = loaded.last_resolved
    last_error_ctx = loaded.source_ctxs[-1].error_ctx
    merged = coerce_flag_fields(merged, schema)
    try:
        result = handle_load_errors(
            func=lambda: transform_to_dataclass(
                loaded.last_source,
                merged,
                schema,
                resolved_type_loaders=last_resolved.type_loaders,
            ),
            ctx=last_error_ctx,
        )
    except DatureConfigError as exc:
        if report is not None:
            attach_load_report(schema, report)
        if loaded.skipped_fields:
            raise enrich_skipped_errors(exc, loaded.skipped_fields) from exc
        raise

    if report is not None:
        attach_load_report(result, report)

    return _MergedData(
        result=result,
        merged_raw=merged,
        last_source=loaded.last_source,
        last_resolved=loaded.last_resolved,
    )


def merge_load_as_function[T: DataclassInstance](
    merge_meta: MergeConfig,
    schema: type[T],
    *,
    debug: bool,
) -> T:
    data = _load_and_merge(
        merge_meta=merge_meta,
        schema=schema,
        debug=debug,
    )

    last_resolved = data.last_resolved
    validating_retort = create_validating_retort(
        data.last_source,
        schema,
        resolved_type_loaders=last_resolved.type_loaders,
    )
    validation_loader = validating_retort.get_loader(schema)

    last_meta = data.last_source
    mask_secrets = resolve_mask_secrets(load_level=merge_meta.mask_secrets)
    secret_paths: frozenset[str] = frozenset()
    if mask_secrets:
        extra_patterns = _collect_extra_secret_patterns(merge_meta)
        secret_paths = build_secret_paths(schema, extra_patterns=extra_patterns)
    last_error_ctx = build_error_ctx(
        last_meta,
        schema.__name__,
        secret_paths=secret_paths,
        mask_secrets=mask_secrets,
    )
    try:
        handle_load_errors(
            func=lambda: validation_loader(data.merged_raw),
            ctx=last_error_ctx,
        )
    except DatureConfigError:
        if debug:
            report = get_load_report(data.result)
            if report is not None:
                attach_load_report(schema, report)
        raise

    return data.result


class _MergePatchContext:
    def __init__(
        self,
        *,
        merge_meta: MergeConfig,
        cls: type[DataclassInstance],
        cache: bool,
        debug: bool,
    ) -> None:
        self._prepare_sources(merge_meta=merge_meta, cls=cls)

        self.merge_meta = merge_meta
        self.cls = cls
        self.cache = cache
        self.debug = debug
        self.cached_data: DataclassInstance | None = None
        self.field_list = fields(cls)
        self.original_init = cls.__init__
        self.original_post_init = getattr(cls, "__post_init__", None)
        self.loading = False
        self.validating = False

        last_source = merge_meta.sources[-1]
        last_resolved = resolve_source_params(
            last_source,
            load_expand_env_vars=merge_meta.expand_env_vars,
            load_type_loaders=merge_meta.type_loaders,
            load_nested_resolve_strategy=merge_meta.nested_resolve_strategy,
            load_nested_resolve=merge_meta.nested_resolve,
        )
        ensure_retort(last_source, cls, resolved_type_loaders=last_resolved.type_loaders)
        validating_retort = create_validating_retort(
            last_source,
            cls,
            resolved_type_loaders=last_resolved.type_loaders,
        )
        self.validation_loader: Callable[[JSONValue], DataclassInstance] = validating_retort.get_loader(cls)

        mask_secrets = resolve_mask_secrets(load_level=merge_meta.mask_secrets)
        self.secret_paths: frozenset[str] = frozenset()
        if mask_secrets:
            extra_patterns = _collect_extra_secret_patterns(merge_meta)
            self.secret_paths = build_secret_paths(cls, extra_patterns=extra_patterns)

        last_meta = merge_meta.sources[-1]
        self.error_ctx = build_error_ctx(
            last_meta,
            cls.__name__,
            secret_paths=self.secret_paths,
            mask_secrets=mask_secrets,
        )

    def _prepare_sources(
        self,
        *,
        merge_meta: MergeConfig,
        cls: type[DataclassInstance],
    ) -> None:
        for source_item in merge_meta.sources:
            resolved = resolve_source_params(
                source_item,
                load_expand_env_vars=merge_meta.expand_env_vars,
                load_type_loaders=merge_meta.type_loaders,
                load_nested_resolve_strategy=merge_meta.nested_resolve_strategy,
                load_nested_resolve=merge_meta.nested_resolve,
            )
            ensure_retort(source_item, cls, resolved_type_loaders=resolved.type_loaders)


def _make_merge_new_init(ctx: _MergePatchContext) -> Callable[..., None]:
    def new_init(self: DataclassInstance, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        if ctx.loading:
            ctx.original_init(self, *args, **kwargs)
            return

        if ctx.cache and ctx.cached_data is not None:
            loaded_data = ctx.cached_data
        else:
            ctx.loading = True
            try:
                merged_data = _load_and_merge(
                    merge_meta=ctx.merge_meta,
                    schema=ctx.cls,
                    debug=ctx.debug,
                )
            finally:
                ctx.loading = False
            loaded_data = merged_data.result
            ctx.error_ctx = build_error_ctx(
                merged_data.last_source,
                ctx.cls.__name__,
                secret_paths=ctx.secret_paths,
                mask_secrets=ctx.error_ctx.mask_secrets,
            )
            if ctx.cache:
                ctx.cached_data = loaded_data

        complete_kwargs = merge_fields(loaded_data, ctx.field_list, args, kwargs)
        ctx.original_init(self, *args, **complete_kwargs)

        if ctx.debug:
            report = get_load_report(loaded_data)
            if report is not None:
                attach_load_report(self, report)

        if ctx.original_post_init is None:
            self.__post_init__()  # type: ignore[attr-defined]

    return new_init


def merge_make_decorator(
    merge_meta: MergeConfig,
    *,
    cache: bool,
    debug: bool,
) -> Callable[[type[DataclassInstance]], type[DataclassInstance]]:
    def decorator(cls: type[DataclassInstance]) -> type[DataclassInstance]:
        if not is_dataclass(cls):
            msg = f"{cls.__name__} must be a dataclass"
            raise TypeError(msg)

        ctx = _MergePatchContext(
            merge_meta=merge_meta,
            cls=cls,
            cache=cache,
            debug=debug,
        )
        cls.__init__ = _make_merge_new_init(ctx)  # type: ignore[method-assign]
        cls.__post_init__ = make_validating_post_init(ctx)  # type: ignore[attr-defined]
        return cls

    return decorator
