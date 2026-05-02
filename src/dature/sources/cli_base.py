import abc
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar, cast

from dature.errors import CaretSpan, SourceLocation
from dature.sources.base import FlatKeySource
from dature.types import (
    JSONValue,
    NestedConflict,
    NestedConflicts,
    NestedResolve,
    NestedResolveStrategy,
)


@dataclass(kw_only=True, repr=False)
class CliSource(FlatKeySource, abc.ABC):
    """Abstract base for CLI argument sources.

    Concrete subclasses (``ArgparseSource`` and user-defined ones for click,
    typer, or custom parsers) implement :meth:`_parse_argv` to convert the
    process's CLI arguments into a flat ``dict[str, JSONValue]``.

    Contract for subclasses:
        - Top-level args go directly under their name.
        - Groups / subcommands emit a discriminator key plus sub-args prefixed
          by the chosen group/subcommand name, joined with ``self.nested_sep``.
        - Non-bool args MUST appear ONLY when explicitly passed by the user;
          unset defaults must NOT leak into the result, otherwise merge
          semantics with other sources break.
        - Bool-style flags appear when their default is meaningful
          (``True``/``False``); a default of ``None`` is treated the same as
          a non-bool unset value and MUST NOT appear, so absence on the CLI
          falls back to the schema/dataclass default.

    The flat dict produced by ``_parse_argv`` is then unfolded into a nested
    structure by :class:`FlatKeySource` using ``nested_sep`` (default ``"--"``,
    so ``--db--host`` nests as ``db.host`` in the dataclass).
    """

    nested_sep: str = "--"
    location_label: ClassVar[str] = "CLI"

    @abc.abstractmethod
    def _parse_argv(self) -> dict[str, JSONValue]:
        """Read CLI args (via the underlying parser) and return a flat dict.

        See class docstring for the contract.
        """

    @cached_property
    def _parsed(self) -> dict[str, JSONValue]:
        return self._parse_argv()

    def _load(self) -> JSONValue:
        return cast("JSONValue", self._parsed)

    def _pre_process_row(
        self,
        key: str,
        value: str,
        result: dict[str, JSONValue],
        conflicts: NestedConflicts,
        *,
        resolved_nested_strategy: NestedResolveStrategy = "flat",
        resolved_nested_resolve: NestedResolve | None = None,
    ) -> None:
        if self.prefix and not key.startswith(self.prefix):
            return

        processed_key = key[len(self.prefix) :] if self.prefix else key
        parts = processed_key.split(self.nested_sep)
        self._process_key_value(
            parts=parts,
            value=value,
            result=result,
            conflicts=conflicts,
            resolved_nested_strategy=resolved_nested_strategy,
            resolved_nested_resolve=resolved_nested_resolve,
        )

    def resolve_location(
        self,
        *,
        field_path: list[str],
        file_content: str | None,  # noqa: ARG002
        nested_conflict: NestedConflict | None,
        input_value: JSONValue = None,  # noqa: ARG002
    ) -> list[SourceLocation]:
        flag_name = self._resolve_var_name(field_path, self.prefix, self.nested_sep, nested_conflict)
        flag_display = f"--{flag_name}"
        line_content = [flag_display]
        line_carets = [CaretSpan(start=0, end=len(flag_display))]
        return [
            SourceLocation(
                location_label=self.location_label,
                file_path=None,
                line_range=None,
                line_content=line_content,
                env_var_name=flag_display,
                line_carets=line_carets,
            ),
        ]
