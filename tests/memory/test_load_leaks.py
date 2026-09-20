"""Retention checks for ``load()`` — function mode, ``Dature``, decorator, and ``Loader.load``.

Two failure shapes are covered:

- ``TestFreshLoadRetainsNothing`` / ``TestReusedLoadRetainsNothing``: after a warmup phase,
  repeated calls must not grow the number of live ``Loader``/``RetortCache``/``Retort``/schema
  instances. A real leak shows up as an unbounded, monotonic count — the warmup absorbs
  one-time costs (``adaptix`` lazy init, ``default_config()`` bootstrap, ``lru_cache`` fills).
- ``TestLoadIsCollectable``: a dropped reference must actually be collectable — no reference
  cycle or external registry keeps it alive. ``TestFreshLoadRetainsNothing`` already asserts
  this indirectly (a stuck reference would show up as live-count growth); this makes the
  "was it collected" question explicit and covers the one shape the growth tests don't build:
  a ``debug=True`` instance with a load report attached.

``reload=`` lifecycle is already covered in ``tests/loading/test_loader.py::TestLoaderReloadLifecycle``
and is out of scope here.
"""

import gc
import weakref

import pytest

from dature.sources.protocol import SourceProtocol
from tests.memory.helpers import (
    COLLECTABLE_FACTORIES,
    FRESH_FACTORIES,
    RETORT_REUSE_FACTORIES,
    EntryFactory,
    live_counts,
)

_WARMUP = 5
_ITERATIONS = 50


class TestFreshLoadRetainsNothing:
    @pytest.mark.parametrize("make_callable", FRESH_FACTORIES)
    def test_repeated_calls_do_not_grow_live_objects(
        self, leak_source: SourceProtocol, make_callable: EntryFactory
    ) -> None:
        fn = make_callable(leak_source)

        for _ in range(_WARMUP):
            fn()
        before = live_counts()

        for _ in range(_ITERATIONS):
            fn()

        assert live_counts() == before


class TestReusedLoadRetainsNothing:
    @pytest.mark.parametrize("make_callable", RETORT_REUSE_FACTORIES)
    def test_repeated_calls_do_not_grow_live_objects(
        self, leak_source: SourceProtocol, make_callable: EntryFactory
    ) -> None:
        fn = make_callable(leak_source)

        for _ in range(_WARMUP):
            fn()
        before = live_counts()

        for _ in range(_ITERATIONS):
            fn()

        assert live_counts() == before


class TestLoadIsCollectable:
    @pytest.mark.parametrize("make_callable", COLLECTABLE_FACTORIES)
    def test_dropped_reference_is_collected(self, leak_source: SourceProtocol, make_callable: EntryFactory) -> None:
        fn = make_callable(leak_source)
        weak = None

        def _make() -> None:
            nonlocal weak
            weak = weakref.ref(fn())

        _make()
        gc.collect()

        assert weak is not None
        assert weak() is None
