"""Model-loader providers that reshape dataclass shapes (defaults, overrides, probe dicts)."""

from collections.abc import Callable, Sequence
from dataclasses import MISSING, fields, is_dataclass, replace
from functools import partial
from typing import get_type_hints

from adaptix import CannotProvide, Loader, Mediator

from dature.loading.default_factory import required_params_of
from dature.protocols import DataclassInstance
from dature.providers._adaptix_compat import (
    DefaultFactory,
    DefaultValue,
    InputShape,
    InputShapeRequest,
    LocatedRequest,
    ModelLoaderProvider,
    NoDefault,
    Param,
    ParamKind,
    provide_generic_resolved_shape,
)
from dature.providers.compiler import _TrackingCompilerMixin
from dature.providers.typed_dict import TypedDictLayoutMixin
from dature.type_aliases import NOT_LOADED, ProbeDict


def _resolved_shape(
    mediator: Mediator[Loader[ProbeDict]],
    request: LocatedRequest[Loader[ProbeDict]],
) -> InputShape[ProbeDict]:
    return provide_generic_resolved_shape(mediator, InputShapeRequest(loc_stack=request.loc_stack))


def _kw_only_params(ids_and_names: "Sequence[tuple[str, str]]") -> tuple[Param, ...]:
    return tuple(Param(field_id=field_id, name=name, kind=ParamKind.KW_ONLY) for field_id, name in ids_and_names)


def _required_dataclass_fields(
    dataclass_type: type[DataclassInstance],
    seen: frozenset[type[DataclassInstance]],
) -> "dict[str, type[DataclassInstance]] | None":
    """Return required init fields of *dataclass_type* mapped to their dataclass types.

    ``None`` when the type cannot be built from defaults alone: a required field is not a
    dataclass that is itself buildable, or the schema is recursive (*seen* guards cycles).
    """
    if dataclass_type in seen:
        return None
    try:
        hints = get_type_hints(dataclass_type)
    except (NameError, TypeError, AttributeError):
        return None
    required: dict[str, type[DataclassInstance]] = {}
    for f in fields(dataclass_type):
        if not f.init or f.default is not MISSING or f.default_factory is not MISSING:
            continue
        nested = hints.get(f.name)
        if not (isinstance(nested, type) and is_dataclass(nested)):
            return None
        if _required_dataclass_fields(nested, seen | {dataclass_type}) is None:
            return None
        required[f.name] = nested
    return required


def _is_buildable_dataclass(field_type: object) -> bool:
    return (
        isinstance(field_type, type)
        and is_dataclass(field_type)
        and _required_dataclass_fields(field_type, frozenset()) is not None
    )


def _build_from_defaults(dataclass_type: type[DataclassInstance]) -> DataclassInstance:
    """Build *dataclass_type*, recursively building its required nested dataclass fields."""
    required = _required_dataclass_fields(dataclass_type, frozenset()) or {}
    return dataclass_type(**{name: _build_from_defaults(nested) for name, nested in required.items()})


def _default_factory_for(dataclass_type: type[DataclassInstance]) -> "DefaultFactory[DataclassInstance]":
    return DefaultFactory(partial(_build_from_defaults, dataclass_type))


class ConstructorOverrideProvider(_TrackingCompilerMixin, ModelLoaderProvider):  # type: ignore[no-untyped-call]
    """Coerce dataclass fields and construct the instance via *constructor_fn* instead of *schema*.

    Required fields stay required and optional fields use their dataclass defaults.
    Only applies to the top-level *schema* type (nested dataclasses are loaded normally).
    Used by ``RetortCache.final_retort`` in decorator mode so that the internal
    ``_dature_constructor`` is called rather than the raw schema constructor.
    """

    def __init__(self, constructor_fn: Callable[..., ProbeDict], schema: type) -> None:
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
        shape = _resolved_shape(mediator, request)
        kw_only_params = _kw_only_params([(f.id, f.id) for f in shape.fields])
        return replace(shape, params=kw_only_params, constructor=self._constructor_fn, kwargs=None)


class RequireUnsafeFactoryFieldsProvider(_TrackingCompilerMixin, ModelLoaderProvider):  # type: ignore[no-untyped-call]
    """Treat a field's un-callable ``default_factory`` as no default at all.

    ``field(default_factory=TgConfig)`` makes ``tg`` optional for adaptix: an absent/unrecognized
    key falls back to calling ``TgConfig()``, which raises a bare ``TypeError`` when ``TgConfig``
    has required constructor arguments. Such a factory can never actually satisfy the field, so
    for loading purposes the field should behave exactly like the same field declared without
    ``default_factory`` — required, with the normal "missing field" error path.

    Applies at every level (root and nested), so a field with an unsafe factory anywhere in the
    schema is affected, not just at the top. Fields whose factory *can* be called with zero
    arguments (``list``, ``dict``, all-defaults dataclasses, zero-arg callables) are left alone.
    No separate applicability check: ``ModelLoaderProvider.provide_loader`` calls ``_fetch_shape``
    first thing, so raising ``CannotProvide`` there when nothing needed changing is enough — no
    need to inspect the type twice.
    """

    def _fetch_shape(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> InputShape[ProbeDict]:
        shape = _resolved_shape(mediator, request)
        changed_ids: set[str] = set()
        new_fields = []
        for f in shape.fields:
            if isinstance(f.default, DefaultFactory) and required_params_of(f.default.factory) is not None:
                new_fields.append(replace(f, is_required=True, default=NoDefault()))
                changed_ids.add(f.id)
            else:
                new_fields.append(f)
        if not changed_ids:
            raise CannotProvide
        # Rebuild every param as KW_ONLY: an optional field can precede the now-required one in
        # declaration order (e.g. ``debug: bool = False`` before ``tg``), which would otherwise
        # break positional ordering.
        new_params = _kw_only_params([(p.field_id, p.name) for p in shape.params])
        return replace(shape, fields=tuple(new_fields), params=new_params)


class ImplicitNestedDefaultProvider(_TrackingCompilerMixin, ModelLoaderProvider):  # type: ignore[no-untyped-call]
    """Treat a nested dataclass buildable without arguments as optional.

    adaptix makes ``inner: InnerConfig`` (no default) required even when ``InnerConfig()`` needs no
    arguments, so an absent key fails with "Missing required field". Giving such a field
    ``DefaultFactory(CorsConfig)`` makes an absent key fall back to the nested defaults. This is
    done on the model shape rather than on the raw dict, so aliases and ``name_style`` keep working.
    """

    def provide_loader(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> Loader[ProbeDict]:
        loc_type = getattr(request.last_loc, "type", None)
        if not (isinstance(loc_type, type) and is_dataclass(loc_type)):
            raise CannotProvide
        return super().provide_loader(mediator, request)  # type: ignore[arg-type]

    def _fetch_shape(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> InputShape[ProbeDict]:
        shape = _resolved_shape(mediator, request)
        if not any(isinstance(f.default, NoDefault) and _is_buildable_dataclass(f.type) for f in shape.fields):
            raise CannotProvide
        new_fields = tuple(
            replace(f, is_required=False, default=_default_factory_for(f.type))
            if isinstance(f.default, NoDefault) and _is_buildable_dataclass(f.type)
            else f
            for f in shape.fields
        )
        # An optional field may now precede a required one, so params must be KW_ONLY.
        new_params = _kw_only_params([(p.field_id, p.name) for p in shape.params])
        return replace(shape, fields=new_fields, params=new_params)


class ModelToDictProvider(_TrackingCompilerMixin, TypedDictLayoutMixin, ModelLoaderProvider):  # type: ignore[no-untyped-call]
    """Converts dataclass model(s) to optional-fields dicts (constructor = dict).

    *exclude* (default empty) lists model types this provider must NOT touch — used for
    ``field_pass(skip=False)`` so that validators on ``Annotated[NestedDC, V.check(...)]`` or
    ``Annotated[list[NestedDC], V.each(...)]`` receive real instances of *those* types, not dicts,
    while every other nested model is still individually pruneable. The probe-mode call site
    (``skip=True``) passes no *exclude* — nested models must all be prunable there.
    """

    def __init__(self, exclude: frozenset[type] = frozenset()) -> None:
        super().__init__()
        self._exclude = exclude

    def provide_loader(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> Loader[ProbeDict]:
        loc_type = getattr(request.last_loc, "type", None)
        if loc_type in self._exclude or not (isinstance(loc_type, type) and is_dataclass(loc_type)):
            raise CannotProvide
        return super().provide_loader(mediator, request)  # type: ignore[arg-type]

    def _fetch_shape(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> InputShape[ProbeDict]:
        shape = super()._fetch_shape(mediator, request)
        optional_fields = tuple(
            replace(
                f,
                is_required=False,
                default=DefaultValue(NOT_LOADED),
            )
            for f in shape.fields
        )
        optional_params = _kw_only_params([(f.id, f.id) for f in optional_fields])
        return replace(
            shape,
            fields=optional_fields,
            params=optional_params,
            constructor=dict,
            kwargs=None,
        )
