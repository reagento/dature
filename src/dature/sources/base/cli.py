import abc
from dataclasses import dataclass
from functools import cached_property
from typing import cast

from dature.errors import CaretSpan, SourceLocation
from dature.sources.base.flat_key import FlatKeySource
from dature.type_aliases import (
    ExpandEnvVarsMode,
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

    ``expand_env_vars`` defaults to ``"disabled"`` (override of the base
    :class:`Source` default): the shell has already expanded ``$VAR`` before
    the value reaches Python, and re-expanding would silently turn quoted
    literals like ``'$ecret'`` into empty strings. Pass ``"default"`` /
    ``"empty"`` / ``"strict"`` explicitly if you want CLI values re-expanded.
    """

    nested_sep: str = "--"
    expand_env_vars: ExpandEnvVarsMode | None = "disabled"
    location_label: str = "CLI"

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

    def _build_var_name(self, key: str) -> str:
        """Build a CLI flag name without uppercasing.

        Overrides :meth:`FlatKeySource._build_var_name` (which uppercases for
        env-var convention). Storing the original case in ``NestedConflict``
        objects also lets :meth:`_resolve_flag_name` compare them correctly
        when reporting the flag in error messages.
        """
        if self.prefix:
            return self.prefix + key
        return key

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
        nested_conflict: NestedConflict | None,
        input_value: JSONValue = None,
        loaded_data: JSONValue | None = None,  # noqa: ARG002
    ) -> list[SourceLocation]:
        flag_name = self._resolve_flag_name(field_path, nested_conflict)
        flag_display = f"--{flag_name}"
        if input_value is not None:
            value_lines = str(input_value).split("\n")
            value_start = len(flag_display) + 1  # after "--flag-name "
            line_content = [f"{flag_display} {value_lines[0]}", *value_lines[1:]]
            line_carets = self._value_line_carets(value_lines, value_start)
        else:
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

    def _resolve_flag_name(
        self,
        field_path: list[str],
        nested_conflict: NestedConflict | None,
    ) -> str:
        """Build the CLI flag name from a field path, preserving its case.

        Mirrors :meth:`FlatKeySource._resolve_var_name` but skips the
        ``.upper()`` step — env-var convention does not apply to CLI flags,
        which users write in their original case (e.g. ``--db--host``).
        """

        def _build(parts: list[str]) -> str:
            name = self.nested_sep.join(parts)
            return self.prefix + name if self.prefix is not None else name

        json_var = _build(field_path[:1])
        if nested_conflict is not None and nested_conflict.used_var == json_var:
            return json_var
        return _build(field_path)
