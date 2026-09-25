import copy
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, is_dataclass, replace
from typing import Any, cast

from adaptix import CannotProvide, Loader, Mediator, Provider, Retort
from adaptix.load_error import LoadError

from dature._adaptix_compat import (
    AlwaysTrueRequestChecker,
    BasicClosureCompiler,
    ClosureCompiler,
    DefaultFactory,
    DefaultValue,
    InputShape,
    InputShapeRequest,
    LoaderRequest,
    LocatedRequest,
    ModelLoaderProvider,
    NoDefault,
    Param,
    ParamKind,
    RequestHandlerRegisterRecord,
    provide_generic_resolved_shape,
)
from dature.loading.default_factory import required_params_of
from dature.nested_dict import collect_not_loaded_paths, remove_path_from_dict
from dature.protocols import DataclassInstance
from dature.type_aliases import NOT_LOADED, JSONValue, NotLoaded, ProbeDict

# Set by ``RetortCache.evict_generated_sources`` while a load is in flight; ``None`` outside of
# it (e.g. when ``cache_engine=True`` and compilation only ever happens once per key). Not
# prefixed with an underscore despite being adaptix-compiler plumbing: ``RetortCache`` (a
# different module) needs to set/reset it around each load. A ``ContextVar`` rather than a plain
# module-level set: it's per-context (thread/async-task), so a concurrent load elsewhere gets its
# own registry and this one is never touched by, or touches, that one.
generated_sources_var: ContextVar[set[str] | None] = ContextVar("_dature_generated_sources", default=None)


class _TrackingCompiler(BasicClosureCompiler):
    """``BasicClosureCompiler`` that records each filename it registers in ``linecache``.

    adaptix's ``_compile`` unconditionally writes the compiled source into the process-global
    ``linecache.cache`` (for traceback readability) and never evicts it — see
    ``adaptix._internal.code_tools.compiler.BasicClosureCompiler._compile`` and
    https://github.com/reagento/adaptix/issues/461. Recording the exact
    key here, at the same place it is written, lets ``RetortCache.evict_generated_sources`` drop
    precisely what the current load compiled, instead of guessing by filename prefix. This is a
    plain subclass used only by the providers below — nothing in adaptix itself is modified or
    patched, so code elsewhere in the process using adaptix directly is entirely unaffected.
    """

    def _compile(self, source: str, unique_filename: str, namespace: dict[str, Any]) -> Any:  # noqa: ANN401
        result = super()._compile(source, unique_filename, namespace)
        registry = generated_sources_var.get()
        if registry is not None:
            registry.add(unique_filename)
        return result


class _TrackingCompilerMixin:
    """Shared ``_get_compiler`` override for every ``ModelLoaderProvider`` subclass dature adds
    to a recipe, so ``_TrackingCompiler`` sees every model dature compiles, not just the
    built-in provider's.
    """

    def _get_compiler(self) -> ClosureCompiler:
        return _TrackingCompiler()


class TrackingModelLoaderProvider(_TrackingCompilerMixin, ModelLoaderProvider):  # type: ignore[no-untyped-call]
    """Drop-in replacement for adaptix's built-in ``ModelLoaderProvider``, tracked for eviction.

    Placed in every recipe (``build_base_recipe``) so it shadows the built-in provider for
    ordinary (non-skip-field) models too — otherwise those would still compile through the
    stock, untracked ``BasicClosureCompiler`` and leak into ``linecache`` regardless of
    ``RetortCache.evict_generated_sources``.

    Restricted to actual dataclasses via ``provide_loader``: adaptix's own ``ModelLoaderProvider``
    matches *any* location (``AnyLocStackChecker``) and only avoids misfiring on non-model types
    like ``ipaddress.IPv4Address``/``uuid.UUID`` because it sits, in the built-in recipe, *after*
    the dedicated providers for those types — first-match-wins. Since ``.extend()`` puts this
    provider *before* all of adaptix's built-ins (including those dedicated providers), it would
    otherwise shadow them too whenever generic shape resolution happens to succeed for such a
    type, producing a structurally-resolvable-but-wrong loader (e.g. expecting a mapping instead
    of a bare string). Explicitly declining anything that isn't a dataclass reproduces the
    built-in's effective scope without depending on recipe order.
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


def _resolved_shape(
    mediator: Mediator[Loader[ProbeDict]],
    request: LocatedRequest[Loader[ProbeDict]],
) -> InputShape[ProbeDict]:
    return provide_generic_resolved_shape(mediator, InputShapeRequest(loc_stack=request.loc_stack))


def _kw_only_params(ids_and_names: "Sequence[tuple[str, str]]") -> tuple[Param, ...]:
    return tuple(Param(field_id=field_id, name=name, kind=ParamKind.KW_ONLY) for field_id, name in ids_and_names)


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


class ModelToDictProvider(_TrackingCompilerMixin, ModelLoaderProvider):  # type: ignore[no-untyped-call]
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
        if loc_type in self._exclude:
            raise CannotProvide
        return super().provide_loader(mediator, request)  # type: ignore[arg-type]

    def _fetch_shape(
        self,
        mediator: Mediator[Loader[ProbeDict]],
        request: LocatedRequest[Loader[ProbeDict]],
    ) -> InputShape[ProbeDict]:
        shape = _resolved_shape(mediator, request)
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
