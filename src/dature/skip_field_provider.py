import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import cast

from adaptix import CannotProvide, Loader, Mediator, Provider, Retort
from adaptix.load_error import LoadError

from dature._adaptix_compat import (
    AlwaysTrueRequestChecker,
    DefaultValue,
    InputShape,
    InputShapeRequest,
    LoaderRequest,
    LocatedRequest,
    ModelLoaderProvider,
    Param,
    ParamKind,
    RequestHandlerRegisterRecord,
    provide_generic_resolved_shape,
)
from dature.nested_dict import collect_not_loaded_paths, remove_path_from_dict
from dature.protocols import DataclassInstance
from dature.type_aliases import NOT_LOADED, JSONValue, NotLoaded, ProbeDict


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


class ConstructorOverrideProvider(ModelLoaderProvider):  # type: ignore[no-untyped-call]
    """Coerce dataclass fields and construct the instance via *constructor_fn* instead of *schema*.

    Required fields stay required and optional fields use their dataclass defaults.
    Only applies to the top-level *schema* type (nested dataclasses are loaded normally).
    Used by ``RetortCache.final_retort`` in decorator mode so that the internal
    ``_dature_constructor`` is called rather than the raw schema constructor.
    """

    def __init__(self, constructor_fn: Callable[..., object], schema: type) -> None:
        super().__init__()
        self._constructor_fn = constructor_fn
        self._schema = schema

    def provide_loader(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> Loader[ProbeDict]:
        loc_type = getattr(request.last_loc, "type", None)
        if loc_type is not self._schema:
            raise CannotProvide
        return super().provide_loader(mediator, request)  # type: ignore[arg-type]

    def _fetch_shape(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> InputShape[ProbeDict]:
        shape = provide_generic_resolved_shape(
            mediator,
            InputShapeRequest(loc_stack=request.loc_stack),
        )
        kw_only_params = tuple(Param(field_id=f.id, name=f.id, kind=ParamKind.KW_ONLY) for f in shape.fields)
        return replace(shape, params=kw_only_params, constructor=self._constructor_fn, kwargs=None)


class ModelToDictProvider(ModelLoaderProvider):  # type: ignore[no-untyped-call]
    """Converts dataclass model(s) to optional-fields dicts (constructor = dict).

    When *schema* is ``None`` (default), applies to ALL model types — used for the
    skip-field probe where nested models must also be individually pruneable.

    When *schema* is a specific type, applies ONLY to that top-level schema and lets
    nested dataclasses be loaded normally.  Used for ``field_pass(skip=False)`` so that
    validators on ``Annotated[NestedDC, V.check(...)]`` receive real instances, not dicts.
    """

    def __init__(self, schema: type | None = None) -> None:
        super().__init__()
        self._schema = schema

    def provide_loader(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> Loader[ProbeDict]:
        if self._schema is not None:
            loc_type = getattr(request.last_loc, "type", None)
            if loc_type is not self._schema:
                raise CannotProvide
        return super().provide_loader(mediator, request)  # type: ignore[arg-type]

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

    probed: ProbeDict = probe_retort.load(raw_dict, schema)  # pyright: ignore[reportAssignmentType]
    all_not_loaded = collect_not_loaded_paths(probed, "")

    skipped: list[str] = []
    for path in all_not_loaded:
        if allowed_fields is not None and path not in allowed_fields:
            continue
        skipped.append(path)

    if not skipped:
        return FilterResult(cleaned_dict=raw_dict, skipped_paths=[])

    cleaned: dict[str, JSONValue] = copy.deepcopy(raw_dict)
    for path in skipped:
        remove_path_from_dict(cleaned, path)

    return FilterResult(cleaned_dict=cleaned, skipped_paths=skipped)
