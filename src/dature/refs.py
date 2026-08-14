"""Cross-source reference placeholder for t-string syntax (Python 3.14+).

Usage (Python 3.14+ only)::

    from dature import ref
    JsonSource(file=t"{ref.env.CONFIG_PATH}")
    VaultSource(host=t"{ref.env.VAULT_HOST}", token=t"{ref.env.VAULT_TOKEN:}")

Equivalent to::

    JsonSource(file="${@env.CONFIG_PATH}")
    VaultSource(host="${@env.VAULT_HOST}", token="${@env.VAULT_TOKEN}")

``ref.tag.key`` returns a :class:`_RefProxy` that records the path.
When dature encounters a t-string in a source init field it reads the proxy's
``parts`` and converts the interpolation to the equivalent ``${@tag.key}``
string, which is then resolved via the normal cross-source pass.

On Python < 3.14 the ``Template`` type does not exist; users must use the
``${@tag.key}`` string syntax instead.
"""

from typing import Final

try:
    from string.templatelib import Template  # type: ignore[import-not-found]

    TEMPLATE_SUPPORTED = True
except ImportError:

    class _Interpolation:
        """Stub mirroring ``string.templatelib.Interpolation`` on Python < 3.14."""

        value: object
        format_spec: str

    class Template:  # type: ignore[no-redef]
        """Stub used on Python < 3.14 where string.templatelib is unavailable."""

        strings: tuple[str, ...]
        interpolations: tuple[_Interpolation, ...]

    TEMPLATE_SUPPORTED = False


class _RefProxy:
    """Proxy that records a dot-separated path for ${@tag.key} resolution."""

    __slots__ = ("_parts",)

    def __init__(self, parts: tuple[str, ...]) -> None:
        self._parts = parts

    def __getattr__(self, name: str) -> "_RefProxy":
        return _RefProxy((*self._parts, name))

    @property
    def parts(self) -> tuple[str, ...]:
        return self._parts

    def __repr__(self) -> str:
        return f"ref.{'.'.join(self._parts)}"

    def to_cross_ref(self, *, default: str | None = None) -> str:
        """Convert to the ${@tag.key} string representation."""
        if len(self._parts) < 2:  # noqa: PLR2004
            msg = f"ref proxy needs at least tag.key but got {self!r}"
            raise ValueError(msg)
        tag = self._parts[0]
        key = ".".join(self._parts[1:])
        if default is not None:
            return f"${{@{tag}.{key}:-{default}}}"
        return f"${{@{tag}.{key}}}"


class _Ref:
    """Singleton that acts as the entry-point for t-string cross-source refs."""

    def __getattr__(self, name: str) -> _RefProxy:
        return _RefProxy((name,))

    def __repr__(self) -> str:
        return "ref"


ref: Final[_Ref] = _Ref()


def template_to_str(template: "Template") -> str:
    """Convert a t-string Template to an equivalent ``${@tag.key}`` string.

    Raises:
        ImportError: if ``string.templatelib`` is unavailable (Python < 3.14).
        TypeError: if *template* is not a ``Template`` instance.
        ValueError: if an interpolation value is not a :class:`_RefProxy`.
    """
    if not TEMPLATE_SUPPORTED:
        msg = 't-string syntax requires Python 3.14+; use "${@tag.key}" syntax instead'
        raise ImportError(msg)

    if not isinstance(template, Template):
        msg = f"expected a t-string Template, got {type(template).__name__!r}"
        raise TypeError(msg)

    parts: list[str] = []
    for i, s in enumerate(template.strings):
        parts.append(s)
        if i < len(template.interpolations):
            interp = template.interpolations[i]
            value = interp.value
            if not isinstance(value, _RefProxy):
                parts.append(str(value))
                continue
            format_spec: str = interp.format_spec or ""
            default = format_spec or None
            parts.append(value.to_cross_ref(default=default))

    return "".join(parts)
