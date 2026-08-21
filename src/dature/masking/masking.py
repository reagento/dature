import re
from collections.abc import Callable, Sequence
from dataclasses import replace

from dature.config import MaskingConfig
from dature.masking.detection import canonical_name, canonical_secret_paths, matches_secret_name
from dature.report_types import FieldOrigin, SourceEntry
from dature.type_aliases import JSONValue

try:
    from random_string_detector import RandomStringDetector  # type: ignore[import-untyped]

    _heuristic_detector: RandomStringDetector | None = RandomStringDetector(allow_numbers=True)
except ImportError:
    _heuristic_detector = None


def mask_value(value: str, masking: MaskingConfig) -> str:
    """Mask *value*, honouring the visible prefix/suffix and mask string from *masking*."""
    if masking.visible_prefix + masking.visible_suffix >= len(value):
        return value
    prefix = value[: masking.visible_prefix] if masking.visible_prefix > 0 else ""
    suffix = value[-masking.visible_suffix :] if masking.visible_suffix > 0 else ""
    return prefix + masking.mask + suffix


def is_secret_path(
    field_path: str | Sequence[str],
    *,
    secret_paths: frozenset[str],
    masking: MaskingConfig,
) -> bool:
    """Return True if *field_path* should be treated as a secret.

    *masking* supplies the effective ``masking_mode`` and, when it is ``"secrets_only"``,
    the heuristic secret-field-name patterns. ``"none"`` never treats anything as secret,
    even an explicitly declared ``secret_paths`` entry.
    """
    match masking.masking_mode:
        case "all":
            return True
        case "none":
            return False
        case "secrets_only":
            pass
        case _ as unknown:
            msg = f"Unknown masking mode: {unknown!r}"
            raise ValueError(msg)
    path = field_path if isinstance(field_path, str) else ".".join(field_path)
    if path in secret_paths:
        return True
    if secret_paths and canonical_name(path) in canonical_secret_paths(secret_paths):
        return True
    return matches_secret_name(path.rpartition(".")[2], masking.secret_field_names)


def mask_json_value(
    data: JSONValue,
    *,
    secret_paths: frozenset[str],
    masking: MaskingConfig,
    _prefix: str = "",
    _force: bool = False,
) -> JSONValue:
    """Recursively mask secret values in *data*.

    *masking* controls the effective ``masking_mode``, mask string, visible prefix/suffix,
    and heuristic thresholds.
    """
    match masking.masking_mode:
        case "none":
            return data
        case "all" | "secrets_only":
            pass
        case _ as unknown:
            msg = f"Unknown masking mode: {unknown!r}"
            raise ValueError(msg)

    if isinstance(data, dict):
        result: dict[str, JSONValue] = {}
        for key, value in data.items():
            child_path = f"{_prefix}.{key}" if _prefix else key
            forced = _force or is_secret_path(child_path, secret_paths=secret_paths, masking=masking)
            result[key] = mask_json_value(
                value,
                secret_paths=secret_paths,
                masking=masking,
                _prefix=child_path,
                _force=forced,
            )
        return result

    if isinstance(data, list):
        return [
            mask_json_value(
                item,
                secret_paths=secret_paths,
                masking=masking,
                _prefix=_prefix,
                _force=_force,
            )
            for item in data
        ]

    if _force or masking.masking_mode == "all":
        return mask_value(data if isinstance(data, str) else str(data), masking)

    if isinstance(data, str) and is_random_string(data, masking):
        return mask_value(data, masking)

    return data


_QUOTED_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
_BARE_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_SCALAR_RE = re.compile(r"[^,{}\[\]\"'\s]+")


def _mask_scalar_token(token: str, masking: MaskingConfig) -> str:
    """Mask *token*, preserving a leading quote pair and any unquoted suffix after it."""
    match = _QUOTED_RE.match(token)
    if match is not None:
        quote = token[0]
        inner = match.group()[1:-1]
        suffix = token[match.end() :]
        return f"{quote}{mask_value(inner, masking)}{quote}{suffix}"
    return mask_value(token, masking)


def _key_end(line: str, after: int, n: int) -> int | None:
    """Return the index just past a `:` starting at *after* (skipping spaces), or None."""
    while after < n and line[after] == " ":
        after += 1
    return after + 1 if after < n and line[after] == ":" else None


def _secret_key_matcher(
    secret_leaf_names: frozenset[str],
    masking: MaskingConfig,
) -> Callable[[str], bool]:
    """Build a predicate for "does this raw key look secret", canonical-name aware."""
    match masking.masking_mode:
        case "secrets_only":
            return lambda key: (
                canonical_name(key) in secret_leaf_names or matches_secret_name(key, masking.secret_field_names)
            )
        case "all" | "none":
            return lambda key: canonical_name(key) in secret_leaf_names
        case _ as unknown:
            msg = f"Unknown masking mode: {unknown!r}"
            raise ValueError(msg)


def _consume_quoted_token(
    line: str,
    i: int,
    n: int,
    *,
    is_secret_key: Callable[[str], bool],
    should_mask: bool,
    masking: MaskingConfig,
) -> tuple[str, int, bool | None]:
    """Consume a quoted token at *i*.

    Returns ``(emitted, next_i, is_secret)``. ``is_secret`` is a bool when the token is a
    key (followed by `:`), or ``None`` when it's a value. An unterminated quote is passed
    through verbatim to the end of the line.
    """
    match = _QUOTED_RE.match(line, i)
    if match is None:
        return (line[i:], n, None)

    token = match.group()
    key_end = _key_end(line, match.end(), n)
    if key_end is not None:
        return (line[i:key_end], key_end, is_secret_key(token[1:-1]))

    text = _mask_scalar_token(token, masking) if should_mask else token
    return (text, match.end(), None)


def _consume_bare_key(
    line: str,
    i: int,
    n: int,
    *,
    is_secret_key: Callable[[str], bool],
) -> tuple[str, int, bool] | None:
    """Consume a bare (unquoted) `key:` at *i*, or return None if *i* isn't one."""
    match = _BARE_KEY_RE.match(line, i)
    if match is None:
        return None
    key_end = _key_end(line, match.end(), n)
    if key_end is None:
        return None
    return (line[i:key_end], key_end, is_secret_key(match.group()))


class _ScanState:
    """Mutable nesting state threaded through a single `_mask_structured_line` scan."""

    __slots__ = ("active_forced", "bare_key_ok", "pending_secret", "stack")

    def __init__(self, *, active_forced: bool) -> None:
        self.stack: list[bool] = []
        self.active_forced = active_forced
        self.bare_key_ok = True
        self.pending_secret = False

    def open_bracket(self, *, is_dict: bool) -> None:
        self.stack.append(self.active_forced)
        self.active_forced = self.active_forced or self.pending_secret
        self.pending_secret = False
        self.bare_key_ok = is_dict

    def close_bracket(self) -> None:
        if self.stack:
            self.active_forced = self.stack.pop()
        self.bare_key_ok = False
        self.pending_secret = False

    def comma(self) -> None:
        self.bare_key_ok = True
        self.pending_secret = False

    @property
    def should_mask_value(self) -> bool:
        return self.pending_secret or (bool(self.stack) and self.active_forced)


def _mask_structured_line(
    line: str,
    *,
    secret_leaf_names: frozenset[str],
    forced: bool,
    masking: MaskingConfig,
) -> str:
    """Mask every secret-eligible value in a `{...}`/`[...]`-bearing line, preserving keys and structure."""
    out: list[str] = []
    i = 0
    n = len(line)
    state = _ScanState(active_forced=forced or masking.masking_mode == "all")
    is_secret_key = _secret_key_matcher(secret_leaf_names, masking)

    while i < n:
        char = line[i]

        if char == " ":
            out.append(char)
            i += 1
            continue

        if char in "{[":
            out.append(char)
            state.open_bracket(is_dict=char == "{")
            i += 1
            continue

        if char in "}]":
            out.append(char)
            state.close_bracket()
            i += 1
            continue

        if char == ",":
            out.append(char)
            state.comma()
            i += 1
            continue

        if char in ('"', "'"):
            text, i, is_secret = _consume_quoted_token(
                line,
                i,
                n,
                is_secret_key=is_secret_key,
                should_mask=state.should_mask_value,
                masking=masking,
            )
            out.append(text)
            state.bare_key_ok = False
            state.pending_secret = False if is_secret is None else is_secret
            continue

        key_result = _consume_bare_key(line, i, n, is_secret_key=is_secret_key) if state.bare_key_ok else None
        if key_result is not None:
            text, i, state.pending_secret = key_result
            out.append(text)
            state.bare_key_ok = False
            continue

        match = _SCALAR_RE.match(line, i)
        if match is not None:
            out.append(_mask_scalar_token(match.group(), masking) if state.should_mask_value else match.group())
            i = match.end()
            state.bare_key_ok = False
            state.pending_secret = False
            continue

        out.append(char)
        i += 1

    return "".join(out)


def mask_env_line(
    line: str,
    *,
    secret_leaf_names: frozenset[str] = frozenset(),
    masking: MaskingConfig,
) -> str:
    match masking.masking_mode:
        case "none":
            return line
        case "all" | "secrets_only":
            pass
        case _ as unknown:
            msg = f"Unknown masking mode: {unknown!r}"
            raise ValueError(msg)
    if "{" in line or "[" in line:
        return _mask_structured_line(
            line,
            secret_leaf_names=secret_leaf_names,
            forced=False,
            masking=masking,
        )
    for sep in ("=", ":"):
        if sep in line:
            key, raw_value = line.split(sep, 1)
            stripped = raw_value.lstrip(" ")
            leading = raw_value[: len(raw_value) - len(stripped)]
            return f"{key}{sep}{leading}{_mask_scalar_token(stripped, masking)}"
    return mask_value(line, masking)


def mask_field_origins(
    origins: tuple[FieldOrigin, ...],
    *,
    secret_paths: frozenset[str],
    masking: MaskingConfig,
) -> tuple[FieldOrigin, ...]:
    match masking.masking_mode:
        case "none":
            return origins
        case "all" | "secrets_only":
            pass
        case _ as unknown:
            msg = f"Unknown masking mode: {unknown!r}"
            raise ValueError(msg)

    return tuple(
        replace(origin, value=mask_value(str(origin.value), masking))
        if is_secret_path(origin.key, secret_paths=secret_paths, masking=masking)
        else origin
        for origin in origins
    )


def mask_source_entries(
    entries: tuple[SourceEntry, ...],
    *,
    secret_paths: frozenset[str],
    masking: MaskingConfig,
) -> tuple[SourceEntry, ...]:
    return tuple(
        replace(
            entry,
            raw_data=mask_json_value(entry.raw_data, secret_paths=secret_paths, masking=masking),
        )
        for entry in entries
    )


def is_random_string(value: str, masking: MaskingConfig) -> bool:
    """Return True when *value* looks like a random/high-entropy string.

    *masking* controls the heuristic thresholds.
    """
    if len(value) < masking.min_heuristic_length:
        return False

    if _heuristic_detector is None:
        return False

    word = value.lower()
    bigrams = [word[i : i + 2] for i in range(len(word) - 1)]
    if not bigrams:
        return False

    uncommon = sum(
        1 for b in bigrams if _heuristic_detector.bigrams.get(b, 0) <= _heuristic_detector.common_bigrams_threshold
    )
    return uncommon / len(bigrams) > masking.heuristic_threshold
