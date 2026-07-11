"""Shared benchmark helpers: env-var setup, timing/memory runners, table printers."""

import gc
import os
import resource
import statistics
import subprocess
import sys
import timeit
import tracemalloc
from pathlib import Path

# Env vars use the BENCH_ prefix to avoid clashing with the real environment. Libraries are
# configured to match (dature: prefix="BENCH_", pydantic-settings: env_prefix="BENCH_", ...).
BENCH_ENV_VARS: dict[str, str] = {
    "BENCH_HOST": "localhost",
    "BENCH_PORT": "5432",
    "BENCH_DEBUG": "true",
    "BENCH_MAX_CONNECTIONS": "100",
    "BENCH_TIMEOUT": "30.5",
    "BENCH_DB_NAME": "mydb",
    "BENCH_WORKERS": "4",
    "BENCH_LOG_LEVEL": "INFO",
}

# Nested schema (prefix BENCH_ND_, "__" nesting): one var per Level5 leaf field.
BENCH_NESTED_ENV_VARS: dict[str, str] = {
    "BENCH_ND_VALUE": "top",
    "BENCH_ND_DEBUG": "true",
    "BENCH_ND_INNER__VALUE": "lvl2",
    "BENCH_ND_INNER__INNER__VALUE": "lvl3",
    "BENCH_ND_INNER__INNER__INNER__VALUE": "lvl4",
    "BENCH_ND_INNER__INNER__INNER__INNER__VALUE": "lvl5",
    "BENCH_ND_INNER__INNER__INNER__INNER__COUNT": "5",
}

# Three independent models, one prefix each.
BENCH_MULTI_ENV_VARS: dict[str, str] = {
    "BENCH_A_FIELD1": "alpha",
    "BENCH_A_FIELD2": "1",
    "BENCH_A_FIELD3": "true",
    "BENCH_B_FIELD1": "beta",
    "BENCH_B_FIELD2": "2",
    "BENCH_B_FIELD3": "false",
    "BENCH_C_FIELD1": "gamma",
    "BENCH_C_FIELD2": "3",
    "BENCH_C_FIELD3": "true",
}

_ALL_ENV_VARS: dict[str, str] = {**BENCH_ENV_VARS, **BENCH_NESTED_ENV_VARS, **BENCH_MULTI_ENV_VARS}

NUMBER = 500
REPEAT = 5
MEM_RUNS = 20
RSS_RUNS = 1000


def set_env_vars() -> None:
    for k, v in _ALL_ENV_VARS.items():
        os.environ[k] = v


def clear_env_vars() -> None:
    for k in _ALL_ENV_VARS:
        os.environ.pop(k, None)


def run_bench(fn) -> tuple[float, float]:
    """Mean ± stddev per call in µs."""
    times = timeit.repeat(fn, number=NUMBER, repeat=REPEAT)
    mean = statistics.mean(times) * 1e6 / NUMBER
    std = statistics.stdev(times) * 1e6 / NUMBER
    return mean, std


def run_mem_bench(fn, warmup: int = 5, runs: int = MEM_RUNS) -> tuple[float, float]:
    """Peak tracemalloc allocation per call, in KiB."""
    for _ in range(warmup):
        fn()
    peaks: list[float] = []
    for _ in range(runs):
        gc.collect()
        tracemalloc.start()
        fn()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak / 1024)
    return statistics.mean(peaks), statistics.stdev(peaks)


def _rss_kib() -> float:
    """Current process max resident set size in KiB (macOS reports bytes, Linux KiB)."""
    v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return v / 1024 if sys.platform == "darwin" else float(v)


def run_rss_bench(fn_name: str, runs: int = RSS_RUNS) -> tuple[float, float]:
    """Retained resident memory per build, in KiB — measured in a fresh subprocess.

    Builds *runs* objects via ``examples.<fn_name>`` keeping every result alive, then reports
    the process RSS high-water-mark growth divided by *runs*. A fresh subprocess is mandatory:
    ``ru_maxrss`` is a monotonic peak, so running many rows in one process would leave later
    rows reading ~0 once an earlier row set the high-water mark. RSS (unlike tracemalloc) counts
    native-extension memory — pydantic_core's Rust core — so it is a fair cross-library metric.
    Reported std is 0.0 (a single aggregate measurement).
    """
    bench_dir = Path(__file__).parent
    src_dir = bench_dir.parent / "src"
    snippet = (
        "import sys, gc\n"
        f"sys.path.insert(0, {str(src_dir)!r}); sys.path.insert(0, {str(bench_dir)!r})\n"
        "import prepare  # noqa: F401 — creates temp files + exports path env vars\n"
        "from _common import set_env_vars, _rss_kib\n"
        "set_env_vars()\n"
        "import examples\n"
        f"fn = examples.{fn_name}\n"
        "fn(); fn()\n"  # warm sys.modules + any lazy init before the baseline
        "gc.collect()\n"
        "before = _rss_kib()\n"
        f"kept = [fn() for _ in range({runs})]\n"
        "gc.collect()\n"
        "after = _rss_kib()\n"
        f"assert len(kept) == {runs}\n"  # keep refs alive so growth is retained, not reclaimed
        f"print(max(0.0, (after - before) / {runs}))\n"
    )
    proc = subprocess.run([sys.executable, "-c", snippet], capture_output=True, text=True, check=True)
    return float(proc.stdout.strip().splitlines()[-1]), 0.0


def _fmt_us(us: float) -> str:
    return f"{us / 1000:.1f} ms" if us >= 1000 else f"{us:.1f} µs"


def _fmt_kib(kib: float) -> str:
    return f"{kib / 1024:.1f} MiB" if kib >= 1024 else f"{kib:.1f} KiB"


def _print_table(title: str, results: list[tuple[str, float, float]], value_fmt, baseline_word: str) -> None:
    sorted_results = sorted(results, key=lambda x: x[1])
    max_label = max(len(r[0]) for r in sorted_results)
    max_mean = max(r[1] for r in sorted_results)
    best = sorted_results[0][1]

    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")
    for label, mean, _std in sorted_results:
        ratio = mean / best if best else 0
        ratio_str = baseline_word if ratio < 1.05 else f"{ratio:.1f}×"
        bar = "█" * max(1, int(mean / max_mean * 20)) if max_mean > 0 else "█"
        print(f"  {label:<{max_label}}  {value_fmt(mean):>10}  {ratio_str:>10}  {bar}")
    print()


def print_table(title: str, results: list[tuple[str, float, float]]) -> None:
    """Speed table; values in µs, each row's unit adapts (ms/µs) to its magnitude."""
    _print_table(title, results, _fmt_us, "baseline")


def print_mem_table(title: str, results: list[tuple[str, float, float]]) -> None:
    """Memory table; values in KiB, each row's unit adapts (MiB/KiB) to its magnitude."""
    _print_table(title, results, _fmt_kib, "baseline")
