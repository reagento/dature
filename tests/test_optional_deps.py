"""Regression tests: optional deps must not be imported at `import dature` time."""

import importlib
import sys

import pytest


@pytest.mark.parametrize(
    "optional_module",
    [
        "json5",
        "ruamel.yaml",
        "toml_rs",
        "random_string_detector",
    ],
)
def test_dature_imports_without_optional_dep(optional_module: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # `sys.modules[name] = None` is the documented way to make `import name` raise ImportError.
    monkeypatch.setitem(sys.modules, optional_module, None)
    # Drop cached dature modules so the next `import dature` re-runs every module-level statement.
    # monkeypatch restores all entries on teardown, so other tests still see the originals.
    for name in [n for n in sys.modules if n == "dature" or n.startswith("dature.")]:
        monkeypatch.delitem(sys.modules, name)

    dature = importlib.import_module("dature")

    # Touch every Source whose loader/path-finder pulls an optional dep —
    # if any of those modules imported the optional dep eagerly, we would have crashed above.
    assert dature.Json5Source.format_name == "json5"
    assert dature.Yaml11Source.format_name == "yaml1.1"
    assert dature.Yaml12Source.format_name == "yaml1.2"
    assert dature.Toml10Source.format_name == "toml1.0"
    assert dature.Toml11Source.format_name == "toml1.1"
