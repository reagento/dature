import re
from typing import Final

from dature.errors.exceptions import CrossRefError, CrossRefExpandError
from dature.type_aliases import JSONValue

# ${@tag.key}, ${@tag.key.nested}, ${@tag.key:-default}
# First alternative is $$ so it is consumed before the brace pattern runs.
_CROSS_RE: Final = re.compile(
    r"\$\$"  # escaped $$ → literal $
    r"|\$\{@([a-zA-Z_]\w*)\.([\w][\w.]*)(?::-((?:[^{}]|\{[^}]*\})*))?\}"
)

CROSS_REF_OPEN: Final = "{@"

_MISSING: Final[object] = object()


def find_refs(text: str) -> list[tuple[str, str]]:
    """Return (tag, key_path) for every unescaped ${@tag.key} in text."""
    result: list[tuple[str, str]] = []
    for m in _CROSS_RE.finditer(text):
        if m.group(0) == "$$":
            continue
        tag, key_path = m.group(1), m.group(2)
        if tag is not None:
            result.append((tag, key_path))
    return result


def needs_cross_ref_expansion(text: str) -> bool:
    """Return True if *text* contains any cross-ref pattern or $$ escape sequence."""
    return bool(_CROSS_RE.search(text))


def _walk_nested(data: dict[str, JSONValue], key_path: str) -> "JSONValue | object":
    """Walk a dot-separated key path through a dict. Returns _MISSING if not found."""
    node: JSONValue = data
    for part in key_path.split("."):
        if not isinstance(node, dict):
            return _MISSING
        if part not in node:
            return _MISSING
        node = node[part]
    return node


class _CrossRefExpander:
    def __init__(
        self,
        *,
        context: dict[str, dict[str, JSONValue]],
        field_path: list[str] | None,
    ) -> None:
        self._context = context
        self._field_path = field_path or []
        self._errors: list[CrossRefError] = []

    def __call__(self, match: re.Match[str]) -> str:
        full = match.group(0)
        if full == "$$":
            return "$"

        tag = match.group(1)
        key_path = match.group(2)
        default = match.group(3)  # None when no :- clause

        if tag not in self._context:
            known = ", ".join(f"'{t}'" for t in sorted(self._context))
            self._errors.append(
                CrossRefError(
                    ref=full,
                    message=f"unknown tag '{tag}'; known tags: {known or 'none'}",
                    field_path=self._field_path,
                )
            )
            return full

        tag_data = self._context[tag]
        value = _walk_nested(tag_data, key_path)

        if value is _MISSING:
            if default is not None:
                return default
            self._errors.append(
                CrossRefError(
                    ref=full,
                    message=f"key '{key_path}' not found in '{tag}' data and no default provided",
                    field_path=self._field_path,
                )
            )
            return full

        if isinstance(value, (dict, list)):
            self._errors.append(
                CrossRefError(
                    ref=full,
                    message=(
                        f"key '{key_path}' in '{tag}' is a {type(value).__name__}; "
                        "only scalar values (str, int, float, bool) are supported"
                    ),
                    field_path=self._field_path,
                )
            )
            return full

        return str(value) if not isinstance(value, bool) else ("true" if value else "false")

    @property
    def errors(self) -> list[CrossRefError]:
        return self._errors


def expand_cross_refs(
    text: str,
    *,
    context: dict[str, dict[str, JSONValue]],
    field_path: list[str] | None = None,
) -> str:
    """Expand every ${@tag.key} (or ${@tag.key:-default}) in text.

    Raises CrossRefExpandError listing all resolution failures.
    $$ is replaced with a literal $.
    """
    expander = _CrossRefExpander(context=context, field_path=field_path)
    result = _CROSS_RE.sub(expander, text)
    if expander.errors:
        msg = "Cross-source reference errors"
        raise CrossRefExpandError(msg, expander.errors)
    return result
