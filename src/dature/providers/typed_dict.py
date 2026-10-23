"""TypedDict support (PEP 728 ``closed`` / ``extra_items``) for dature's adaptix recipes.

adaptix only recognises ``typing.TypedDict`` (by metaclass), silently drops unknown keys and
knows nothing about ``__closed__`` / ``__extra_items__``. The helpers here recognise any
TypedDict (stdlib or ``typing_extensions``) by duck-typing, build its input shape themselves and
translate the PEP 728 metadata into adaptix's extra-data policies:

* ``extra_items=T``  — unknown keys are kept, values are loaded as ``T``;
* ``closed=False``   — unknown keys are kept as they are;
* ``closed=True``    — unknown keys raise ``ExtraFieldsLoadError``;
* neither            — unknown keys are dropped (adaptix default).
"""

import typing
from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Any, get_type_hints

from adaptix import CannotProvide, Loader, Mediator

from dature.providers._adaptix_compat import (
    ExtraCollect,
    ExtraForbid,
    ExtraSaturate,
    InpDictCrown,
    InputField,
    InputNameLayout,
    InputShape,
    LoaderRequest,
    LocatedRequest,
    ModelLoaderProvider,
    NoDefault,
    Param,
    ParamKind,
)
from dature.providers.compiler import _TrackingCompilerMixin
from dature.type_aliases import ProbeDict


def is_typed_dict(tp: object) -> bool:
    """Check that *tp* was built by the TypedDict metaclass of ``typing`` or ``typing_extensions``.

    ``typing.is_typeddict`` only accepts the stdlib metaclass, so it misses
    ``typing_extensions`` TypedDicts. ``typing_extensions.is_typeddict`` would accept both but
    requires importing that module, which is not a dependency of dature. Inspecting the
    metaclass by name gets both without an import: the class object is already built, so its
    metaclass is reachable regardless of whether the module is still in ``sys.modules``.
    """
    metaclass = type(tp)
    return metaclass.__name__ == "_TypedDictMeta" and metaclass.__module__ in ("typing", "typing_extensions")


def _extra_items_type(tp: type) -> object | None:
    """Return the ``extra_items`` annotation of *tp*, or ``None`` when it declares none.

    ``typing_extensions`` always puts ``__extra_items__`` on the classes it builds, holding its
    ``NoExtraItems`` singleton unless an annotation was given. That module is not a dependency of
    dature and may already be gone from ``sys.modules``, so the sentinel is matched by identity
    against stdlib ``typing`` first and by its type's name second.
    """
    extra = getattr(tp, "__extra_items__", None)
    if extra is getattr(typing, "NoExtraItems", None):
        return None
    sentinel_type = type(extra)
    if sentinel_type.__name__ == "NoExtraItemsType" and sentinel_type.__module__ == "typing_extensions":
        return None
    return extra


def build_typed_dict_shape(tp: type) -> "InputShape[ProbeDict]":
    type_hints = sorted(get_type_hints(tp, include_extras=True).items(), key=lambda item: item[0])
    required_keys = tp.__required_keys__  # type: ignore[attr-defined]
    return InputShape(
        constructor=tp,
        fields=tuple(
            InputField(
                type=hint,
                id=name,
                default=NoDefault(),
                is_required=name in required_keys,
                metadata=MappingProxyType({}),
                original=None,
            )
            for name, hint in type_hints
        ),
        params=tuple(Param(field_id=name, name=name, kind=ParamKind.KW_ONLY) for name, _ in type_hints),
        kwargs=None,
        overridden_types=frozenset(),
    )


class TypedDictLayoutMixin:
    """``_fetch_shape`` / ``_fetch_name_layout`` overrides for ``ModelLoaderProvider`` subclasses.

    Both methods fall back to the inherited implementation for non-TypedDict types, so the mixin
    can also be mixed into providers that match every location (``ModelToDictProvider``).
    """

    def _fetch_shape(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> "InputShape[ProbeDict]":
        if not is_typed_dict(request.last_loc.type):
            return super()._fetch_shape(mediator, request)  # type: ignore[misc, no-any-return]
        return build_typed_dict_shape(request.last_loc.type)

    def _fetch_name_layout(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
        shape: "InputShape[ProbeDict]",
    ) -> InputNameLayout:
        layout: InputNameLayout = super()._fetch_name_layout(mediator, request, shape)  # type: ignore[misc]
        crown = layout.crown
        tp = request.last_loc.type
        if not isinstance(crown, InpDictCrown) or not is_typed_dict(tp):
            return layout

        extra_type = _extra_items_type(tp)
        closed = getattr(tp, "__closed__", None)

        if extra_type is not None:
            saturator = _make_saturator(_extra_loader(mediator, request, extra_type))
        elif closed is False:
            saturator = _make_saturator(None)
        elif closed is True:
            return replace(layout, crown=replace(crown, extra_policy=ExtraForbid()), extra_move=None)
        else:
            return layout

        return replace(layout, crown=replace(crown, extra_policy=ExtraCollect()), extra_move=ExtraSaturate(saturator))


class TypedDictModelLoaderProvider(_TrackingCompilerMixin, TypedDictLayoutMixin, ModelLoaderProvider):  # type: ignore[no-untyped-call]
    """``ModelLoaderProvider`` for TypedDicts (stdlib and ``typing_extensions``, PEP 728 aware).

    Restricted to TypedDicts via ``provide_loader``: like ``TrackingModelLoaderProvider``, it sits
    ahead of adaptix's built-ins in the recipe and would otherwise shadow the dedicated providers
    for scalar types such as ``uuid.UUID``.
    """

    def provide_loader(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> Loader[ProbeDict]:
        if not is_typed_dict(getattr(request.last_loc, "type", None)):
            raise CannotProvide
        return super().provide_loader(mediator, request)  # type: ignore[arg-type]


def _extra_loader(
    mediator: Mediator[Loader[ProbeDict]],
    request: LocatedRequest[Loader[ProbeDict]],
    extra_type: object,
) -> "Loader[Any]":
    return mediator.mandatory_provide(
        LoaderRequest(loc_stack=request.loc_stack.replace_last_type(extra_type)),
    )


def _make_saturator(loader: "Loader[Any] | None") -> Any:  # noqa: ANN401
    def saturate(result: dict[str, Any], extra: Mapping[str, Any]) -> None:
        for key, value in extra.items():
            result[key] = value if loader is None else loader(value)

    return saturate
