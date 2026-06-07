"""Helpers for optional-dependency guards with human-readable error messages."""

import importlib


def require_dep(package: str, extra: str) -> None:
    """Raise a helpful ImportError if *package* is not importable.

    Args:
        package: The top-level package name to probe (e.g. ``"ruamel.yaml"``).
        extra: The dature extras name that provides it (e.g. ``"yaml"``).

    Raises:
        ImportError: If *package* cannot be imported, with installation instructions.
    """
    try:
        importlib.import_module(package)
    except ImportError:
        msg = f"'{package}' is not installed. Run: pip install 'dature[{extra}]'"
        raise ImportError(msg) from None
