import logging
import os
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path

from dature.expansion.env_expand import expand_string_collect
from dature.type_aliases import ConfigDirsArg

logger = logging.getLogger("dature")


def _expand_entry(entry: Path | str) -> Iterator[Path]:
    """Expand one ``config_dirs`` entry into zero or more ``Path``s.

    ``Path`` entries are yielded as-is with ``~`` expanded. ``str`` entries
    additionally undergo ``$VAR`` / ``${VAR}`` / ``${VAR:-default}`` expansion
    and are split by ``os.pathsep`` so a ``PATH``-style env var (such as
    ``XDG_CONFIG_DIRS=/a:/b``) resolves to multiple directories. If the entry
    references an undefined environment variable without a fallback, it is
    skipped and a warning is logged.
    """
    if isinstance(entry, Path):
        yield entry.expanduser()
        return

    expanded, errors = expand_string_collect(entry, mode="strict")
    if errors:
        for err in errors:
            logger.warning(
                "config_dirs: environment variable %r is not set; skipping entry %r",
                err.var_name,
                entry,
            )
        return

    for part in expanded.split(os.pathsep):
        if part:
            yield Path(part).expanduser()


def _resolve_dirs(config_dirs: "ConfigDirsArg | None") -> Iterator[Path]:
    """Resolve ``config_dirs`` into concrete ``Path``s for the current platform."""
    if config_dirs is None:
        return

    if isinstance(config_dirs, Mapping):
        entries = config_dirs.get(sys.platform)
        if entries is None:
            return
    else:
        entries = config_dirs

    if isinstance(entries, (str, Path)):
        entries = (entries,)

    for entry in entries:
        yield from _expand_entry(entry)


def find_config(
    filename: str,
    config_dirs: ConfigDirsArg | None,
) -> Path | None:
    """Find the first existing ``filename`` in ``config_dirs``.

    Returns ``None`` when no match is found or when ``config_dirs`` is
    ``None`` or empty (which happens for a ``FileFieldMixin`` accessed before
    ``apply_source_init_params`` has merged defaults from ``LoadingConfig``).
    """
    for d in _resolve_dirs(config_dirs):
        candidate = d / filename
        if candidate.exists():
            return candidate
    return None
