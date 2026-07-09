"""Import benchmark — the one-time cost of importing each library, measured honestly.

Import cost is easy to overstate: a fat virtualenv (many packages on ``sys.path``) slows the
import machinery, and part of any import is really the stdlib the library pulls in. So this
script measures each library in its **own clean venv** (only that package installed), with the
common stdlib **pre-imported**, so the number is the library's own marginal import cost.

Each sample runs in a fresh subprocess, timed/measured inside it. Speed in ms, memory as
tracemalloc peak in MiB.

Run: uv run --group benchmarks python benchmarks/bench_import.py
"""

import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import print_mem_table, print_table

# Common stdlib a config library tends to pull in; pre-imported so we measure the marginal
# cost of the library itself, not the stdlib it triggers.
STDLIB_PREIMPORT = (
    "import typing, dataclasses, abc, collections, collections.abc, functools, itertools, "
    "enum, re, warnings, inspect, contextlib, decimal, fractions, datetime, uuid, pathlib, "
    "json, os, sys"
)

SPEED_RUNS = 30
MEM_RUNS = 10

# (label, pip package, import module)
CASES: list[tuple[str, str, str]] = [
    ("adaptix", "adaptix", "adaptix"),
    ("dature", "dature", "dature"),
    ("pydantic-settings", "pydantic-settings", "pydantic_settings"),
]

UV = shutil.which("uv") or "uv"


def _make_venv(pkg: str) -> Path:
    venv = Path(tempfile.mkdtemp(prefix="bench_imp_"))
    subprocess.run([UV, "venv", "-q", str(venv)], check=True)
    subprocess.run([UV, "pip", "install", "-q", "--python", str(venv / "bin" / "python"), pkg], check=True)
    return venv


def _sample(py: Path, snippet: str, runs: int) -> list[float]:
    out = []
    for _ in range(runs):
        proc = subprocess.run([str(py), "-c", snippet], capture_output=True, text=True, check=True)
        out.append(float(proc.stdout.strip().splitlines()[-1]))
    return out


def measure(py: Path, module: str) -> tuple[float, float, float, float]:
    speed_snip = (
        f"import time\n{STDLIB_PREIMPORT}\nt = time.perf_counter()\nimport {module}\nprint(time.perf_counter() - t)\n"
    )
    mem_snip = (
        f"import gc, tracemalloc\n{STDLIB_PREIMPORT}\ngc.collect()\ntracemalloc.start()\n"
        f"import {module}\n_, peak = tracemalloc.get_traced_memory()\ntracemalloc.stop()\nprint(peak / 1024)\n"
    )
    speed = _sample(py, speed_snip, SPEED_RUNS)
    mem = _sample(py, mem_snip, MEM_RUNS)
    # speed returned in µs (print_table rescales), memory in KiB (print_mem_table rescales)
    return statistics.mean(speed) * 1e6, statistics.stdev(speed) * 1e6, statistics.mean(mem), statistics.stdev(mem)


def main() -> None:
    speed_rows: list[tuple[str, float, float]] = []
    mem_rows: list[tuple[str, float, float]] = []
    venvs: list[Path] = []
    try:
        for label, pkg, module in CASES:
            venv = _make_venv(pkg)
            venvs.append(venv)
            s_mean, s_std, m_mean, m_std = measure(venv / "bin" / "python", module)
            speed_rows.append((label, s_mean, s_std))
            mem_rows.append((label, m_mean, m_std))

        print("\n" + "#" * 72)
        print("  IMPORT cost — clean per-library venv, stdlib pre-imported (marginal)")
        print("#" * 72)
        print_table("Import speed", speed_rows)
        print_mem_table("Import memory (peak)", mem_rows)
    finally:
        for venv in venvs:
            shutil.rmtree(venv, ignore_errors=True)


if __name__ == "__main__":
    main()
