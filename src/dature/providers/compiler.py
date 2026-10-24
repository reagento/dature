"""Compiler plumbing shared by every model-loader provider dature adds to a recipe."""

from contextvars import ContextVar
from dataclasses import is_dataclass
from typing import Any

from adaptix import CannotProvide, Loader, Mediator

from dature.providers._adaptix_compat import (
    BasicClosureCompiler,
    ClosureCompiler,
    LocatedRequest,
    ModelLoaderProvider,
)
from dature.type_aliases import ProbeDict

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
