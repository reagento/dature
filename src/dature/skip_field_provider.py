import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import cast

from adaptix import Retort
from adaptix._internal.common import Loader
from adaptix._internal.model_tools.definitions import DefaultValue, InputShape, Param, ParamKind
from adaptix._internal.morphing.model.loader_provider import ModelLoaderProvider
from adaptix._internal.morphing.request_cls import LoaderRequest
from adaptix._internal.provider.essential import Mediator, Provider, RequestHandlerRegisterRecord
from adaptix._internal.provider.located_request import LocatedRequest
from adaptix._internal.provider.request_checkers import AlwaysTrueRequestChecker
from adaptix._internal.provider.shape_provider import InputShapeRequest, provide_generic_resolved_shape
from adaptix.load_error import LoadError

from dature.protocols import DataclassInstance
from dature.types import NOT_LOADED, JSONValue, NotLoaded, ProbeDict


class SkipFieldProvider(Provider):
    @staticmethod
    def _wrap_handler(
        mediator: Mediator[Loader[JSONValue | NotLoaded]],
        _request: LoaderRequest,
    ) -> Callable[[JSONValue], JSONValue | NotLoaded]:
        next_handler = mediator.provide_from_next()

        def chain_handler(data: JSONValue) -> JSONValue | NotLoaded:
            try:
                return cast("JSONValue", next_handler(data))
            except (LoadError, ValueError, TypeError):
                return NOT_LOADED

        return chain_handler

    def get_request_handlers(self) -> Sequence[RequestHandlerRegisterRecord]:
        return [(LoaderRequest, AlwaysTrueRequestChecker(), self._wrap_handler)]


class ModelToDictProvider(ModelLoaderProvider):  # type: ignore[no-untyped-call]
    def _fetch_shape(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> InputShape[ProbeDict]:
        shape = provide_generic_resolved_shape(
            mediator,
            InputShapeRequest(loc_stack=request.loc_stack),
        )
        optional_fields = tuple(
            replace(
                f,
                is_required=False,
                default=DefaultValue(NOT_LOADED),
            )
            for f in shape.fields
        )
        optional_params = tuple(Param(field_id=f.id, name=f.id, kind=ParamKind.KW_ONLY) for f in optional_fields)
        return replace(
            shape,
            fields=optional_fields,
            params=optional_params,
            constructor=dict,
            kwargs=None,
        )


def _collect_not_loaded_paths(data: ProbeDict, prefix: str) -> list[str]:
    paths: list[str] = []

    for key, value in data.items():
        current_path = f"{prefix}.{key}" if prefix else key
        if value is NOT_LOADED:
            paths.append(current_path)
        elif isinstance(value, dict):
            paths.extend(_collect_not_loaded_paths(value, current_path))

    return paths


def _remove_path_from_dict(data: dict[str, JSONValue], path: str) -> None:
    parts = path.split(".")
    current: dict[str, JSONValue] = data
    for part in parts[:-1]:
        next_val = current.get(part)
        if not isinstance(next_val, dict):
            return
        current = next_val

    current.pop(parts[-1], None)


@dataclass(frozen=True, slots=True)
class FilterResult:
    cleaned_dict: JSONValue
    skipped_paths: list[str]


def filter_invalid_fields(
    raw_dict: JSONValue,
    probe_retort: Retort,
    schema: type[DataclassInstance],
    allowed_fields: set[str] | None,
) -> FilterResult:
    if not isinstance(raw_dict, dict):
        return FilterResult(cleaned_dict=raw_dict, skipped_paths=[])

    probed: ProbeDict = probe_retort.load(raw_dict, schema)
    all_not_loaded = _collect_not_loaded_paths(probed, "")

    skipped: list[str] = []
    for path in all_not_loaded:
        if allowed_fields is not None and path not in allowed_fields:
            continue
        skipped.append(path)

    if not skipped:
        return FilterResult(cleaned_dict=raw_dict, skipped_paths=[])

    cleaned: dict[str, JSONValue] = copy.deepcopy(raw_dict)
    for path in skipped:
        _remove_path_from_dict(cleaned, path)

    return FilterResult(cleaned_dict=cleaned, skipped_paths=skipped)
