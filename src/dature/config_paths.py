import os
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path


def get_system_config_dirs() -> Iterator[Path]:
    """Yield system config directories for current platform in priority order.

    User-specific directories first, then system-wide. On Windows only
    ``%APPDATA%`` (if set) is yielded.
    """
    home = Path.home()

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            yield Path(appdata)
        return

    if sys.platform == "darwin":
        yield home / "Library" / "Application Support"

    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    yield Path(xdg_home) if xdg_home else home / ".config"

    yield Path("/etc")

    xdg_dirs = os.environ.get("XDG_CONFIG_DIRS")
    if xdg_dirs:
        for d in xdg_dirs.split(os.pathsep):
            yield Path(d)
    else:
        yield Path("/etc/xdg")


def find_config(
    filename: str,
    system_config_dirs: Iterable[Path] | None = None,
) -> Path | None:
    """Find first existing config file in standard locations.

    Args:
        filename: Config filename to search for.
        system_config_dirs: Optional custom directories. If ``None``,
            auto-detects based on platform.

    Returns:
        Path to first existing config file, or ``None`` if not found.
    """
    dirs = system_config_dirs if system_config_dirs is not None else get_system_config_dirs()
    for d in dirs:
        candidate = d / filename
        if candidate.exists():
            return candidate
    return None
