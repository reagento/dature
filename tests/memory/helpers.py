"""Shared helpers for tests/memory — retention checks around ``load()``.

Two things live here:

- The tracked-type object counter (``live_counts``) and the tracemalloc retained-memory
  helper (``retained_kib``), used to detect growth after a warmup phase.
- The entry-point factories (``FRESH_FACTORIES``), one per public
  way to call ``load`` — function mode, ``Dature``, decorator, and a reused ``Loader`` —
  so both the object-count and the tracemalloc tests exercise the same surface.
"""

import gc
import json
import tracemalloc
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from adaptix import Retort

from dature import (
    Dature,
    EnvFileSource,
    EnvSource,
    IniSource,
    JsonSource,
    Loader,
    Toml11Source,
    Yaml12Source,
    load,
)
from dature.loading.retort import RetortCache, _DualRetort
from dature.sources.protocol import SourceProtocol


@dataclass
class LeakConfig:
    host: str
    port: int
    debug: bool
    workers: int


_ENV_VARS = {
    "LEAK_HOST": "localhost",
    "LEAK_PORT": "8080",
    "LEAK_DEBUG": "true",
    "LEAK_WORKERS": "4",
}


def _env_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EnvSource:  # noqa: ARG001
    for key, value in _ENV_VARS.items():
        monkeypatch.setenv(key, value)
    return EnvSource(prefix="LEAK_")


def _env_file_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EnvFileSource:  # noqa: ARG001
    path = tmp_path / "leak.env"
    path.write_text("\n".join(f"{key}={value}" for key, value in _ENV_VARS.items()))
    return EnvFileSource(file=path, prefix="LEAK_")


def _json_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JsonSource:  # noqa: ARG001
    path = tmp_path / "leak.json"
    path.write_text(json.dumps({"host": "localhost", "port": 8080, "debug": True, "workers": 4}))
    return JsonSource(file=path)


def _yaml_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Yaml12Source:  # noqa: ARG001
    path = tmp_path / "leak.yaml"
    path.write_text("host: localhost\nport: 8080\ndebug: true\nworkers: 4\n")
    return Yaml12Source(file=path)


def _toml_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Toml11Source:  # noqa: ARG001
    path = tmp_path / "leak.toml"
    path.write_text('[leak]\nhost = "localhost"\nport = 8080\ndebug = true\nworkers = 4\n')
    return Toml11Source(file=path, prefix="leak")


def _ini_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IniSource:  # noqa: ARG001
    path = tmp_path / "leak.ini"
    path.write_text("[leak]\nhost = localhost\nport = 8080\ndebug = true\nworkers = 4\n")
    return IniSource(file=path, prefix="leak")


# Static (non-remote) source kinds, covering both format_loaders() flavours that
# build_base_recipe() actually branches on: string-value (Env/EnvFile/Ini) vs. plain (Json/Yaml/Toml).
SOURCE_BUILDERS: dict[str, Callable[[Path, pytest.MonkeyPatch], SourceProtocol]] = {
    "env": _env_source,
    "env_file": _env_file_source,
    "json": _json_source,
    "yaml": _yaml_source,
    "toml": _toml_source,
    "ini": _ini_source,
}


# Object types a leak in the load path would grow: the Loader itself, its retort machinery,
# and the schema instances it produces. Tracked by name (not identity) so a diff prints the
# offending class directly instead of an opaque count mismatch.
TRACKED_TYPES: tuple[type, ...] = (Loader, RetortCache, _DualRetort, Retort, LeakConfig)


def live_counts() -> "Counter[str]":
    """Snapshot of how many tracked-type instances are currently reachable."""
    gc.collect()
    gc.collect()
    counts: Counter[str] = Counter()
    for obj in gc.get_objects():
        if isinstance(obj, TRACKED_TYPES):
            counts[type(obj).__name__] += 1
    return counts


def retained_kib(fn: Callable[[], object], *, runs: int) -> float:
    """Growth in tracemalloc-traced memory across *runs* calls to *fn*, after ``gc.collect()``.

    Deliberately reads ``current`` (not ``peak``) — the per-call allocation churn is already
    covered by ``benchmarks/bench_memory.py``; this measures what survives a full collection,
    which is what a leak actually looks like.
    """
    gc.collect()
    tracemalloc.start()
    try:
        before, _ = tracemalloc.get_traced_memory()
        for _ in range(runs):
            fn()
        gc.collect()
        after, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return (after - before) / 1024


EntryFactory = Callable[[SourceProtocol], Callable[[], Any]]


def _function_mode(source: SourceProtocol) -> Callable[[], Any]:
    return lambda: load(source, schema=LeakConfig)


def _function_mode_dature(source: SourceProtocol) -> Callable[[], Any]:
    return lambda: Dature().load(source, schema=LeakConfig)


def _loader_mode(source: SourceProtocol) -> Callable[[], Any]:
    return lambda: Loader(source, schema=LeakConfig).load()


def _loader_mode_dature(source: SourceProtocol) -> Callable[[], Any]:
    return lambda: Dature().loader(source, schema=LeakConfig).load()


def _loader_mode_cache_engine(source: SourceProtocol) -> Callable[[], Any]:
    return lambda: Loader(source, schema=LeakConfig, cache_engine=True).load()


def _debug_mode(source: SourceProtocol) -> Callable[[], Any]:
    return lambda: load(source, schema=LeakConfig, debug=True)


# Each factory builds everything from scratch on every call — the throwaway-Loader path
# (`dature.load(...)` and friends) that must retain nothing between calls.
FRESH_FACTORIES: list[Any] = [
    pytest.param(_function_mode, id="function"),
    pytest.param(_function_mode_dature, id="function_dature"),
    pytest.param(_loader_mode, id="loader"),
    pytest.param(_loader_mode_dature, id="loader_dature"),
    pytest.param(_loader_mode_cache_engine, id="loader_cache_engine"),
]

# Same throwaway shape, plus the one case FRESH_FACTORIES doesn't cover: debug=True attaches
# a load report to the returned instance (report.py::attach_load_report) — worth checking that
# reference doesn't keep the instance alive past a dropped weakref.
COLLECTABLE_FACTORIES: list[Any] = [*FRESH_FACTORIES, pytest.param(_debug_mode, id="debug_instance")]


def _decorator_reused(**loader_kwargs: Any) -> EntryFactory:
    def build(source: SourceProtocol) -> Callable[[], Any]:
        settings_cls: Callable[[], Any] = load(source, **loader_kwargs)(LeakConfig)
        return settings_cls

    return build


def _decorator_reused_dature(**loader_kwargs: Any) -> EntryFactory:
    def build(source: SourceProtocol) -> Callable[[], Any]:
        settings_cls: Callable[[], Any] = Dature().load(source, **loader_kwargs)(LeakConfig)
        return settings_cls

    return build


def _loader_reused(**loader_kwargs: Any) -> EntryFactory:
    def build(source: SourceProtocol) -> Callable[[], Any]:
        loader = Loader(source, schema=LeakConfig, **loader_kwargs)
        return loader.load

    return build


# Each factory builds one long-lived object (a decorated class or a Loader) and returns a
# callable that only exercises the hot re-load path — catches state accumulating inside the
# Loader/RetortCache/decorator itself, not just throwaway-construction leaks.
RETORT_REUSE_FACTORIES: list[Any] = [
    pytest.param(_decorator_reused(), id="decorator"),
    pytest.param(_decorator_reused(cache=True), id="decorator_cached"),
    pytest.param(_decorator_reused(cache_engine=True), id="decorator_cache_engine"),
    pytest.param(_decorator_reused_dature(), id="decorator_dature"),
    pytest.param(_loader_reused(cache=True), id="loader_cached"),
    pytest.param(_loader_reused(cache=timedelta(minutes=5)), id="loader_ttl"),
    pytest.param(_loader_reused(cache=False), id="loader_no_cache"),
]
