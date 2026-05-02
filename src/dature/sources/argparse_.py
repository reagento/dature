import argparse
from dataclasses import dataclass
from functools import cached_property
from typing import Any, ClassVar

from dature.sources.cli_base import CliSource
from dature.types import JSONValue

_BoolActionTypes = (
    argparse._StoreTrueAction,  # noqa: SLF001
    argparse._StoreFalseAction,  # noqa: SLF001
    argparse.BooleanOptionalAction,
)


@dataclass(kw_only=True, repr=False)
class ArgparseSource(CliSource):
    """CLI source backed by a user-supplied :class:`argparse.ArgumentParser`.

    The parser reads ``sys.argv[1:]`` itself via ``parse_args()``. Supports
    arbitrary nesting of subparsers: the chosen subparser's name is emitted
    under the subparsers action's ``dest`` (the discriminator), and its
    arguments are emitted under a prefix equal to the subparser name, joined
    with ``self.nested_sep``.

    Example::

        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int)
        subs = parser.add_subparsers(dest="command")
        create = subs.add_parser("create")
        create.add_argument("--name")

        @dataclass
        class CreateArgs:
            name: str

        @dataclass
        class Config:
            command: str
            port: int = 8000
            create: CreateArgs | None = None

        config = load(ArgparseSource(parser=parser), schema=Config)
    """

    parser: argparse.ArgumentParser
    format_name: ClassVar[str] = "argparse"

    @cached_property
    def _ns(self) -> argparse.Namespace:
        saved = self._suppress_unset_defaults(self.parser)
        try:
            return self.parser.parse_args()
        finally:
            self._restore_defaults(saved)

    def _parse_argv(self) -> dict[str, JSONValue]:
        out: dict[str, JSONValue] = {}
        self._flatten_namespace(self._ns, self.parser, prefix=[], out=out)
        return out

    @classmethod
    def _suppress_unset_defaults(
        cls,
        parser: argparse.ArgumentParser,
    ) -> dict[argparse.Action, Any]:
        """Replace defaults with ``argparse.SUPPRESS`` so they don't leak into output.

        For non-bool actions: any default is suppressed (their meaningful value
        is "explicitly passed by the user").

        For bool actions: only ``default=None`` is suppressed. A bool action
        with an explicit ``True``/``False`` default is treated as meaningful
        and kept (e.g. ``store_true`` whose argparse default is ``False`` still
        emits ``False`` when the flag is not passed).
        """
        saved: dict[argparse.Action, Any] = {}
        for action in parser._actions:  # noqa: SLF001
            if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
                for subparser in action.choices.values():
                    saved.update(cls._suppress_unset_defaults(subparser))
                continue
            if action.default is argparse.SUPPRESS:
                continue
            is_bool = isinstance(action, _BoolActionTypes)
            if is_bool and action.default is not None:
                continue
            saved[action] = action.default
            action.default = argparse.SUPPRESS
        return saved

    @staticmethod
    def _restore_defaults(saved: dict[argparse.Action, Any]) -> None:
        for action, default in saved.items():
            action.default = default

    def _action_key(self, action: argparse.Action) -> str:
        """Derive the flat-dict key for an action.

        Argparse rewrites ``-`` to ``_`` in ``dest``, which destroys the
        nested-separator structure for flags like ``--db--host``. If any
        long-form option string contains the separator inside its name,
        we use it directly to preserve the structure; otherwise the
        already-derived ``dest`` is fine.
        """
        for opt in action.option_strings:
            if opt.startswith("--"):
                stripped = opt.lstrip("-")
                if self.nested_sep in stripped:
                    return stripped
        return action.dest

    def _flatten_namespace(
        self,
        ns: argparse.Namespace,
        parser: argparse.ArgumentParser,
        *,
        prefix: list[str],
        out: dict[str, JSONValue],
    ) -> None:
        sep = self.nested_sep
        for action in parser._actions:  # noqa: SLF001
            if action.dest in (None, argparse.SUPPRESS, "help"):
                continue
            if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
                chosen_name = getattr(ns, action.dest, None)
                if chosen_name is None:
                    continue
                out[sep.join([*prefix, action.dest])] = chosen_name
                chosen_parser = action.choices.get(chosen_name)
                if chosen_parser is not None:
                    self._flatten_namespace(
                        ns,
                        chosen_parser,
                        prefix=[*prefix, chosen_name],
                        out=out,
                    )
            elif hasattr(ns, action.dest):
                out[sep.join([*prefix, self._action_key(action)])] = getattr(ns, action.dest)
