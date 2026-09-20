"""tracemalloc safety net for ``load()`` — catches retained memory that ``live_counts()``
would miss because it lives inside ``adaptix`` internals rather than a ``dature`` type.

Complements ``tests/memory/test_load_leaks.py``: that file's strict object-count equality is
the main gate, this is a tolerant fallback for growth that never surfaces as a `dature`-owned
object. Scoped to ``RETORT_REUSE_FACTORIES`` — the entry points that build one long-lived
Loader/decorator and call ``.load()`` repeatedly on it; see its docstring in ``helpers.py`` for
why the fresh-Retort-per-call case (``loader_no_cache``) belongs here too.
"""

import pytest

from dature.sources.protocol import SourceProtocol
from tests.memory.helpers import RETORT_REUSE_FACTORIES, EntryFactory, retained_kib

_WARMUP = 5
_RUNS = 100

# A real leak on this path retains kilobytes per call, i.e. hundreds of KiB over `_RUNS` calls.
# 64 KiB gives headroom over observed format-parser noise (ruamel.yaml/configparser/tomllib
# allocate per-call state that isn't `dature`'s to free) without masking a regression.
_MAX_RETAINED_KIB = 64.0


class TestLoadAllocationIsFlat:
    @pytest.mark.parametrize("make_callable", RETORT_REUSE_FACTORIES)
    def test_reused_calls_do_not_retain_memory(self, leak_source: SourceProtocol, make_callable: EntryFactory) -> None:
        fn = make_callable(leak_source)

        for _ in range(_WARMUP):
            fn()

        retained = retained_kib(fn, runs=_RUNS)

        assert retained < _MAX_RETAINED_KIB
