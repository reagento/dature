"""Run all benchmarks and print a combined report.

Usage:
    uv run --group benchmarks python benchmarks/run_all.py
"""

import subprocess
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).parent
SCRIPTS = [
    "bench_env.py",
    "bench_file_json.py",
    "bench_file_toml.py",
    "bench_file_yaml.py",
    "bench_file_env.py",
    "bench_multi_source.py",
    "bench_caching.py",
]


def main() -> None:
    print(f"\n{'#' * 66}")
    print("  dature benchmarks vs pydantic-settings / python-decouple / dynaconf / hydra")
    print(f"{'#' * 66}")
    print(f"  Python {sys.version.split()[0]}")

    for script in SCRIPTS:
        path = BENCH_DIR / script
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=False,
            check=False,
        )
        if result.returncode != 0:
            print(f"\n[FAILED] {script} exited with code {result.returncode}")

    print(f"\n{'#' * 66}\n")


if __name__ == "__main__":
    main()
