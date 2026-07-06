"""Shared fixtures and utilities for all benchmark scripts."""

import json
import os
import statistics
import timeit
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BenchConfig:
    host: str
    port: int
    debug: bool
    max_connections: int
    timeout: float
    db_name: str
    workers: int
    log_level: str


# Typed data used for file-based sources (JSON/TOML/YAML parse native types)
BENCH_DATA: dict = {
    "host": "localhost",
    "port": 5432,
    "debug": True,
    "max_connections": 100,
    "timeout": 30.5,
    "db_name": "mydb",
    "workers": 4,
    "log_level": "INFO",
}

# Env var names use BENCH_ prefix to avoid clashing with real environment variables.
# Libraries are configured to match this prefix (dature: prefix="BENCH_",
# pydantic-settings: env_prefix="BENCH_", dynaconf: envvar_prefix="BENCH").
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

NUMBER = 500
REPEAT = 5


def set_env_vars() -> None:
    for k, v in BENCH_ENV_VARS.items():
        os.environ[k] = v


def clear_env_vars() -> None:
    for k in BENCH_ENV_VARS:
        os.environ.pop(k, None)


def write_json(path: Path) -> None:
    path.write_text(json.dumps(BENCH_DATA))


def write_toml(path: Path) -> None:
    lines: list[str] = []
    for k, v in BENCH_DATA.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, str):
            lines.append(f'{k} = "{v}"')
        else:
            lines.append(f"{k} = {v}")
    path.write_text("\n".join(lines) + "\n")


def write_yaml(path: Path) -> None:
    lines: list[str] = []
    for k, v in BENCH_DATA.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {v}")
    path.write_text("\n".join(lines) + "\n")


def write_dotenv(path: Path) -> None:
    lines = [f"{k[len('BENCH_') :]}={v}" for k, v in BENCH_ENV_VARS.items()]
    path.write_text("\n".join(lines) + "\n")


def run_bench(fn) -> tuple[float, float]:
    times = timeit.repeat(fn, number=NUMBER, repeat=REPEAT)
    mean = statistics.mean(times) * 1e6 / NUMBER
    std = statistics.stdev(times) * 1e6 / NUMBER
    return mean, std


def print_table(title: str, results: list[tuple[str, float, float]]) -> None:
    sorted_results = sorted(results, key=lambda x: x[1])
    max_label = max(len(r[0]) for r in sorted_results)
    max_mean = max(r[1] for r in sorted_results)
    fastest = sorted_results[0][1]

    print(f"\n{'=' * 66}")
    print(f"  {title}")
    print(f"{'=' * 66}")
    print(f"  {'Library':<{max_label}}  {'Mean':>8}  {'±Std':>7}  {'vs fastest':>10}")
    print(f"  {'-' * max_label}  {'--------':>8}  {'-------':>7}  {'----------':>10}")
    for label, mean, std in sorted_results:
        ratio = mean / fastest
        ratio_str = "baseline" if ratio < 1.05 else f"{ratio:.1f}×"
        bar_len = max(1, int(mean / max_mean * 24))
        bar = "█" * bar_len
        print(f"  {label:<{max_label}}  {mean:7.1f} µs  ±{std:5.1f}  {ratio_str:>10}  {bar}")
    print()
