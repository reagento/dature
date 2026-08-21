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


def _resolve_brace_default(content: str, full: str) -> str:
    separator = ":-"
    idx = content.find(separator)
    if idx != -1:
        var_name = content[:idx]
        fallback = content[idx + len(separator) :]
        value = os.environ.get(var_name)
        if value is not None:
            return value
        return expand_string_default(fallback)

    value = os.environ.get(content)
    if value is not None:
        return value
    return full


def _resolve_simple_default(var_name: str, full: str) -> str:
    value = os.environ.get(var_name)
    if value is not None:
        return value
    return full


class _EnvExpander:
    def __init__(self, *, mode: ExpandEnvVarsMode, source_text: str) -> None:
        self._mode: ExpandEnvVarsMode = mode
        self._source_text = source_text
        self._errors: list[MissingEnvVarError] = []

    @property
    def errors(self) -> list[MissingEnvVarError]:
        return self._errors

    def __call__(self, match: re.Match[str]) -> str:
        full = match.group(0)

        if full == "$$":
            # Preserve $$ immediately before {@ so the cross-source pass can
            # collapse it to a literal $, keeping ${@...} as a plain string.
            if match.string[match.end() : match.end() + 2] == CROSS_REF_OPEN:
                return "$$"
            return "$"
        if full == "%%":
            return "%"

        brace_content = match.group(1)
        dollar_name = match.group(2)
        percent_name = match.group(3)

        if brace_content is not None:
            return self._resolve_brace(brace_content, match.start())
        if dollar_name is not None:
            return self._resolve_var(dollar_name, match.start())
        return self._resolve_var(percent_name, match.start())

    def _resolve_brace(self, content: str, position: int) -> str:
        separator = ":-"
        idx = content.find(separator)
        if idx != -1:
            var_name = content[:idx]
            fallback = content[idx + len(separator) :]
            value = os.environ.get(var_name)
            if value is not None:
                return value
            return expand_string(fallback, mode=self._mode)

        return self._resolve_var(content, position)

    def _resolve_var(self, var_name: str, position: int) -> str:
        value = os.environ.get(var_name)
        if value is not None:
            return value

        if self._mode == "strict":
            self._errors.append(
                MissingEnvVarError(
                    var_name=var_name,
                    position=position,
                    source_text=self._source_text,
                ),
            )

        return ""


def expand_string(text: str, *, mode: ExpandEnvVarsMode) -> str:
    match mode:
        case "disabled":
            return text
        case "default":
            return expand_string_default(text)
        case "empty" | "strict":
            pass
        case _ as unknown:
            msg = f"Unknown expand_env_vars mode: {unknown!r}"
            raise ValueError(msg)

    expander = _EnvExpander(mode=mode, source_text=text)
    result = _VAR_RE.sub(expander, text)

    if expander.errors:
        msg = "Missing environment variables"
        raise EnvVarExpandError(msg, expander.errors)

    return result


def expand_string_collect(text: str, *, mode: ExpandEnvVarsMode) -> tuple[str, list[MissingEnvVarError]]:
    """Expand string and return (result, errors) without raising."""
    match mode:
        case "disabled":
            return text, []
        case "default":
            return expand_string_default(text), []
        case "empty" | "strict":
            pass
        case _ as unknown:
            msg = f"Unknown expand_env_vars mode: {unknown!r}"
            raise ValueError(msg)

    expander = _EnvExpander(mode=mode, source_text=text)
    result = _VAR_RE.sub(expander, text)
    return result, expander.errors


def expand_string_default(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        full = match.group(0)

        if full == "$$":
            if match.string[match.end() : match.end() + 2] == CROSS_REF_OPEN:
                return "$$"
            return "$"
        if full == "%%":
            return "%"

        brace_content = match.group(1)
        if brace_content is not None:
            return _resolve_brace_default(brace_content, full)

        var_name = match.group(2) or match.group(3)
        if var_name is not None:
            return _resolve_simple_default(var_name, full)

        return full

    return _VAR_RE.sub(_replace, text)


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
        return expand_string(data, mode=mode)

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
        result, errs = expand_string_collect(data, mode=mode)
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
        return [_expand_recursive_collect(item, mode=mode, path=path, errors=errors) for item in data]

    return data
