import logging
import os
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from dature.expansion.env_expand import _expand_string_collect

if TYPE_CHECKING:
    from dature.types import SystemConfigDirsArg

logger = logging.getLogger("dature")


def _expand_entry(entry: Path | str) -> Iterator[Path]:
    """Expand one ``system_config_dirs`` entry into zero or more ``Path``s.

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

    expanded, errors = _expand_string_collect(entry, mode="strict")
    if errors:
        for err in errors:
            logger.warning(
                "system_config_dirs: environment variable %r is not set; skipping entry %r",
                err.var_name,
                entry,
            )
        return

    for part in expanded.split(os.pathsep):
        if part:
            yield Path(part).expanduser()


def _resolve_dirs(system_config_dirs: "SystemConfigDirsArg | None") -> Iterator[Path]:
    """Resolve ``system_config_dirs`` into concrete ``Path``s for the current platform."""
    if system_config_dirs is None:
        return

    if isinstance(system_config_dirs, Mapping):
        entries = system_config_dirs.get(sys.platform)
        if entries is None:
            return
    else:
        entries = system_config_dirs

    for entry in entries:
        yield from _expand_entry(entry)


def find_config(
    filename: str,
    system_config_dirs: "SystemConfigDirsArg | None",
) -> Path | None:
    """Find the first existing ``filename`` in ``system_config_dirs``.

    Returns ``None`` when no match is found or when ``system_config_dirs`` is
    ``None`` (which happens for a ``FileFieldMixin`` accessed before
    ``_apply_source_init_params`` has merged defaults from ``LoadingConfig``).
    """
    for d in _resolve_dirs(system_config_dirs):
        candidate = d / filename
        if candidate.exists():
            return candidate
    return None
