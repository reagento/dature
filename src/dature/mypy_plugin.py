"""mypy plugin that makes @load()-decorated dataclass fields optional in __init__.

When @load() is used as a decorator, it replaces __init__ so all field
values are loaded from configuration sources.  Without this plugin mypy
reports ``call-arg`` errors on ``Config()`` because the original dataclass
signature still requires every field.

Usage — add to your ``mypy`` configuration::

    [tool.mypy]
    plugins = ["dature.mypy_plugin"]
"""

from collections.abc import Callable

from mypy.nodes import ARG_NAMED_OPT, ARG_STAR, ARG_STAR2
from mypy.options import Options
from mypy.plugin import ClassDefContext, FunctionSigContext, Plugin
from mypy.types import CallableType, FunctionLike

_LOAD_FULLNAMES: frozenset[str] = frozenset(
    {
        "dature.load",
        "dature.main.load",
    },
)


def _make_args_optional(sig: CallableType) -> CallableType:
    new_arg_kinds = []
    for kind in sig.arg_kinds:
        if kind in (ARG_STAR, ARG_STAR2):
            new_arg_kinds.append(kind)
        else:
            new_arg_kinds.append(ARG_NAMED_OPT)
    return sig.copy_modified(arg_kinds=new_arg_kinds)


class DaturePlugin(Plugin):
    def __init__(self, options: Options) -> None:
        super().__init__(options)
        self._load_decorated_classes: set[str] = set()

    def get_class_decorator_hook(
        self,
        fullname: str,
    ) -> Callable[[ClassDefContext], None] | None:
        if fullname in _LOAD_FULLNAMES:
            return self._tag_load_decorated
        return None

    def _tag_load_decorated(self, ctx: ClassDefContext) -> None:
        self._load_decorated_classes.add(ctx.cls.fullname)

    def get_function_signature_hook(
        self,
        fullname: str,
    ) -> Callable[[FunctionSigContext], FunctionLike] | None:
        if fullname in self._load_decorated_classes:
            return _adjust_init_signature
        return None


def _adjust_init_signature(ctx: FunctionSigContext) -> FunctionLike:
    return _make_args_optional(ctx.default_signature)


def plugin(version: str) -> type[Plugin]:  # noqa: ARG001
    return DaturePlugin
