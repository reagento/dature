import os
import re
from pathlib import Path

from dature.errors import EnvVarExpandError, MissingEnvVarError
from dature.expansion.cross_source import CROSS_REF_OPEN
from dature.type_aliases import ExpandEnvVarsMode, FilePath, JSONValue

# $VAR, ${VAR}, ${VAR:-default}, %VAR%, $$, %%
# Note: ${@...} is intentionally excluded (negative lookahead) — cross-source refs
# are handled by expansion/cross_source.py and must survive this pass intact.
_VAR_RE = re.compile(
    r"\$\$"  # escaped $$
    r"|%%"  # escaped %%
    r"|\$\{(?!@)([^}]+)\}"  # ${VAR} or ${VAR:-default}, NOT ${@tag.key}
    r"|\$([A-Za-z_][A-Za-z0-9_]*)"  # $VAR
    r"|%([A-Za-z_][A-Za-z0-9_]*)%",  # %VAR%
)


def _validate_mode(mode: ExpandEnvVarsMode) -> None:
    if mode not in ("disabled", "default", "empty", "strict"):
        msg = f"Unknown expand_env_vars mode: {mode!r}"
        raise ValueError(msg)


class _EnvExpander:
    """Resolve ``_VAR_RE`` matches for one of ``default``/``empty``/``strict``.

    ``default`` and ``empty`` never raise or record ``self._errors``; only ``strict``
    collects a ``MissingEnvVarError`` per missing variable. The caller decides whether
    to raise on those errors (``expand_string``) or return them (``expand_string_collect``).
    """

    def __init__(
        self,
        *,
        mode: ExpandEnvVarsMode,
        source_text: str,
        preserve_cross_refs: bool = True,
    ) -> None:
        self._mode: ExpandEnvVarsMode = mode
        self._source_text = source_text
        self._preserve_cross_refs = preserve_cross_refs
        self._errors: list[MissingEnvVarError] = []

    @property
    def errors(self) -> list[MissingEnvVarError]:
        return self._errors

    def __call__(self, match: re.Match[str]) -> str:
        full = match.group(0)

        if full == "$$":
            # Preserve $$ immediately before {@ so a later cross-source pass can
            # collapse it to a literal $, keeping ${@...} as a plain string. Only
            # relevant for source init-fields, which get that second pass — config
            # data values never do, so there $$ must always collapse to $.
            if self._preserve_cross_refs and match.string[match.end() : match.end() + 2] == CROSS_REF_OPEN:
                return "$$"
            return "$"
        if full == "%%":
            return "%"

        brace_content = match.group(1)
        dollar_name = match.group(2)
        percent_name = match.group(3)

        if brace_content is not None:
            return self._resolve_brace(brace_content, full, match.start())
        if dollar_name is not None:
            return self._resolve_var(dollar_name, full, match.start())
        return self._resolve_var(percent_name, full, match.start())

    def _resolve_brace(self, content: str, full: str, position: int) -> str:
        var_name, separator, fallback = content.partition(":-")
        value = os.environ.get(var_name)
        if value is not None:
            return value
        if not separator:
            return self._on_missing(var_name, full, position)

        # Recurse through this same expander (not a fresh one) so that a missing
        # variable inside the fallback contributes to this call's own error list
        # instead of raising from a throwaway sub-expander (see changes/ bugfix
        # fragment for the nested-fallback fix this replaced).
        return _VAR_RE.sub(self, fallback)

    def _resolve_var(self, var_name: str, full: str, position: int) -> str:
        value = os.environ.get(var_name)
        if value is not None:
            return value
        return self._on_missing(var_name, full, position)

    def _on_missing(self, var_name: str, full: str, position: int) -> str:
        if self._mode == "default":
            return full

        if self._mode == "strict":
            self._errors.append(
                MissingEnvVarError(
                    var_name=var_name,
                    position=position,
                    source_text=self._source_text,
                ),
            )

        return ""


def _expand(text: str, *, mode: ExpandEnvVarsMode, preserve_cross_refs: bool) -> tuple[str, list[MissingEnvVarError]]:
    _validate_mode(mode)
    if mode == "disabled":
        return text, []

    expander = _EnvExpander(mode=mode, source_text=text, preserve_cross_refs=preserve_cross_refs)
    result = _VAR_RE.sub(expander, text)
    return result, expander.errors


def expand_string(text: str, *, mode: ExpandEnvVarsMode, preserve_cross_refs: bool = True) -> str:
    result, errors = _expand(text, mode=mode, preserve_cross_refs=preserve_cross_refs)
    if errors:
        msg = "Missing environment variables"
        raise EnvVarExpandError(msg, errors)
    return result


def expand_string_collect(
    text: str,
    *,
    mode: ExpandEnvVarsMode,
    preserve_cross_refs: bool = True,
) -> tuple[str, list[MissingEnvVarError]]:
    """Expand string and return (result, errors) without raising."""
    return _expand(text, mode=mode, preserve_cross_refs=preserve_cross_refs)


def expand_string_default(text: str, *, preserve_cross_refs: bool = True) -> str:
    result, _ = _expand(text, mode="default", preserve_cross_refs=preserve_cross_refs)
    return result


def expand_file_path(file_path: FilePath, *, mode: ExpandEnvVarsMode) -> str:
    expanded = expand_string(str(file_path), mode=mode)
    if isinstance(file_path, Path):
        return str(Path(expanded))
    return expanded


def expand_env_vars(data: JSONValue, *, mode: ExpandEnvVarsMode) -> JSONValue:
    match mode:
        case "disabled":
            return data
        case "default" | "empty":
            return _expand_recursive(data, mode=mode)
        case "strict":
            pass
        case _ as unknown:
            msg = f"Unknown expand_env_vars mode: {unknown!r}"
            raise ValueError(msg)

    all_errors: list[MissingEnvVarError] = []
    result = _expand_recursive_collect(data, mode=mode, path=[], errors=all_errors)
    if all_errors:
        msg = "Missing environment variables"
        raise EnvVarExpandError(msg, all_errors)
    return result


def _expand_recursive(data: JSONValue, *, mode: ExpandEnvVarsMode) -> JSONValue:
    if isinstance(data, str):
        # Config data values never get a second (cross-source) expansion pass, unlike
        # source init-fields — so $$ must always collapse to a literal $ here, even
        # right before {@, or it would leak through as $${@...} to the final value.
        return expand_string(data, mode=mode, preserve_cross_refs=False)

    if isinstance(data, dict):
        return {key: _expand_recursive(value, mode=mode) for key, value in data.items()}

    if isinstance(data, list):
        return [_expand_recursive(item, mode=mode) for item in data]

    return data


def _expand_recursive_collect(
    data: JSONValue,
    *,
    mode: ExpandEnvVarsMode,
    path: list[str],
    errors: list[MissingEnvVarError],
) -> JSONValue:
    if isinstance(data, str):
        result, errs = expand_string_collect(data, mode=mode, preserve_cross_refs=False)
        for err in errs:
            err.field_path = list(path)
        errors.extend(errs)
        return result

    if isinstance(data, dict):
        return {
            key: _expand_recursive_collect(value, mode=mode, path=[*path, key], errors=errors)
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [
            _expand_recursive_collect(item, mode=mode, path=[*path, str(i)], errors=errors)
            for i, item in enumerate(data)
        ]

    return data
