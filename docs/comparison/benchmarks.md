# Performance Benchmarks

Comparison of dature against pydantic-settings, python-decouple, dynaconf, and hydra, split
into three independent costs:

1. **Import** — the one-time cost of importing the library into a process. Measured in a clean
   per-library venv (see below), because it's easy to overstate.
2. **Build + load** — one full cycle with nothing reused: declare the model, build the source
   and loader, load. This is what "function mode" pays on every call.
3. **Warm reuse** — dature only: the hot path once the loader is built once and reused, or cached.

## Methodology

**Import** (`bench_import.py`) — each library is measured in its **own fresh virtualenv** with
only that package installed, and the common stdlib is **pre-imported** first, so the number is
the library's own marginal import cost. Measuring inside the project's benchmark venv would
overstate it roughly 2× — a large `site-packages` slows Python's import machinery, and part of
any import is really the stdlib the library pulls in. Each sample is a fresh subprocess timed
inside itself; speed in ms, memory as `tracemalloc` peak in MiB.

**Build + load** and **Warm reuse** (`bench_speed.py`, `bench_memory.py`) — in-process,
`timeit.repeat(number=500, repeat=5)` for speed and `tracemalloc` peak for memory. The library
is already imported (a warmup call warms `sys.modules`), so these numbers exclude import and
capture only the per-call work. Every library re-declares its model class each call, so it's
apples-to-apples.

`tracemalloc` tracks the Python heap only; pydantic-settings uses a Rust extension
(`pydantic_core`) whose allocations are invisible here, so its memory numbers are understated.

Machine: Apple M3, Python 3.13.13.
Schema (flat): 8 fields — `host: str`, `port: int`, `debug: bool`, `max_connections: int`,
`timeout: float`, `db_name: str`, `workers: int`, `log_level: str`.
Library versions: pydantic-settings 2.14.2 · python-decouple 3.8 · dynaconf 3.2.13 · hydra-core 1.3.3.

```bash
uv sync --group benchmarks
uv run --group benchmarks python benchmarks/bench_import.py
uv run --group benchmarks python benchmarks/bench_speed.py
uv run --group benchmarks python benchmarks/bench_memory.py
```

The `vs` columns are ratios to the best value **in that column** (speed and memory have
independent baselines).

---

## 1. Import (one-time, per process)

Clean per-library venv, stdlib pre-imported.

| Library | Import speed | vs | Import memory | vs |
|---------|-------------:|---:|--------------:|---:|
| pydantic-settings | 108.7 ms | baseline | 12.1 MiB | 1.5× |
| adaptix (dature's engine) | 122.1 ms | 1.1× | 8.3 MiB | baseline |
| dature | 152.9 ms | 1.4× | 11.5 MiB | 1.4× |

dature imports in ~153 ms and ~11.5 MiB — about 1.4× pydantic-settings on time, and slightly
**lighter** on memory. Most of dature's import is adaptix (its type engine, ~122 ms); dature's
own code adds ~30 ms. This is a one-time cost paid once per process, not per config load.

---

## 2. Build + load (per fresh load, import excluded)

One full cycle with nothing reused. Rows ordered by speed.

### ENV (`os.environ` → typed dataclass)

| Library | Speed | vs | Memory | vs |
|---------|------:|---:|-------:|---:|
| python-decouple | 156 µs | baseline | 150.3 KiB | 3.7× |
| pydantic-settings | 304 µs | 1.9× | 40.5 KiB | baseline |
| dature (func) | 1.6 ms | 10.3× | 808.8 KiB | 20.0× |
| dature (decorator) | 1.6 ms | 10.5× | 814.9 KiB | 20.1× |
| dynaconf | 9.9 ms | 63.4× | 176.8 KiB | 4.4× |

### ENV file (`.env` → typed dataclass)

| Library | Speed | vs | Memory | vs |
|---------|------:|---:|-------:|---:|
| python-decouple | 707 µs | baseline | 151.8 KiB | 2.4× |
| pydantic-settings | 1.0 ms | 1.4× | 64.4 KiB | baseline |
| dature (func) | 2.8 ms | 3.9× | 806.8 KiB | 12.5× |
| dature (decorator) | 3.0 ms | 4.2× | 812.9 KiB | 12.6× |
| dynaconf | 17.2 ms | 24.3× | 251.7 KiB | 3.9× |

### JSON file

| Library | Speed | vs | Memory | vs |
|---------|------:|---:|-------:|---:|
| pydantic-settings | 529 µs | baseline | 47.2 KiB | baseline |
| dature (func) | 2.5 ms | 4.7× | 802.4 KiB | 17.0× |
| dature (decorator) | 2.7 ms | 5.1× | 817.7 KiB | 17.3× |
| dynaconf | 5.5 ms | 10.4× | 152.4 KiB | 3.2× |

*python-decouple: no JSON file support.*

### TOML file

| Library | Speed | vs | Memory | vs |
|---------|------:|---:|-------:|---:|
| pydantic-settings | 711 µs | baseline | 47.4 KiB | baseline |
| dature (decorator) | 2.7 ms | 3.8× | 819.8 KiB | 17.3× |
| dature (func) | 2.7 ms | 3.9× | 804.6 KiB | 17.0× |
| dynaconf | 5.5 ms | 7.7× | 151.7 KiB | 3.2× |

*python-decouple: no TOML file support.*

### YAML file

| Library | Speed | vs | Memory | vs |
|---------|------:|---:|-------:|---:|
| pydantic-settings | 1.3 ms | baseline | 59.4 KiB | baseline |
| dature (func) | 3.4 ms | 2.7× | 813.9 KiB | 13.7× |
| dature (decorator) | 3.5 ms | 2.7× | 829.1 KiB | 14.0× |
| dynaconf | 6.3 ms | 5.0× | 164.7 KiB | 2.8× |
| hydra (DictConfig, not typed) | 18.2 ms | 14.5× | 502.6 KiB | 8.5× |

*python-decouple: no YAML file support. hydra returns an `OmegaConf DictConfig`, not a typed dataclass.*

### Nested model, 5 levels deep (ENV source)

Five dataclasses nested five levels deep (`Level1.inner → … → Level5`), from `__`-joined env keys.

| Library | Speed | vs | Memory | vs |
|---------|------:|---:|-------:|---:|
| pydantic-settings | 681 µs | baseline | 77.3 KiB | baseline |
| dature (func) | 3.3 ms | 4.8× | 567.9 KiB | 7.3× |
| dature (decorator) | 3.4 ms | 5.0× | 575.2 KiB | 7.4× |

*python-decouple / hydra: no schema-driven nested model from ENV.*

### Three models loaded at once (ENV source)

| Library | Speed | vs | Memory | vs |
|---------|------:|---:|-------:|---:|
| pydantic-settings | 578 µs | baseline | 60.7 KiB | baseline |
| dature (decorator) | 3.2 ms | 5.6× | 672.5 KiB | 11.1× |
| dature (func) | 3.2 ms | 5.6× | 586.1 KiB | 9.7× |
| dynaconf | 14.0 ms | 24.2× | 211.9 KiB | 3.5× |

On a fresh build, dature is ~2.5–5× slower than pydantic-settings and allocates far more
(~0.6–0.8 MiB vs tens of KiB) because it constructs a fresh adaptix retort — full type analysis
of the schema — on every call. pydantic-settings rebuilds its (Rust-backed) schema too but is
cheaper at it. This is the price of function mode; it's not how dature is meant to run in a hot
path (see below). pydantic-settings' memory is also understated (Rust core invisible to `tracemalloc`).

---

## 3. Warm reuse

Hot path once the loader is built at module level, and with caching. The steady state of a
long-running service.

Both dature (loader built once) and pydantic-settings (schema cached on the class) are measured
re-loading over their pre-built object.

| Mode | Speed | vs | Memory | vs |
|------|------:|---:|-------:|---:|
| dature — `cache=True` (eternal) | 1.2 µs | baseline | 1.0 KiB | baseline |
| dature — `cache=timedelta(...)` (TTL) | 1.2 µs | baseline | 1.1 KiB | baseline |
| dature — `Loader` reuse | 98.7 µs | 81.1× | 11.4 KiB | 11.1× |
| dature — decorator, hot | 101.8 µs | 83.6× | 11.7 KiB | 11.4× |
| pydantic-settings — reuse | 112.6 µs | 92.5× | 20.8 KiB | 20.3× |

In steady state the ranking flips versus build+load: dature (loader reused) is a touch **faster**
than pydantic-settings reused (~99 µs vs ~113 µs) and about half the memory (11.4 vs 20.8 KiB).
Caching drops dature to ~1.2 µs / ~1 KiB — ~90× faster than either. `cache=timedelta` adds
automatic TTL expiry a plain `@lru_cache` wrapper can't do.

---

## Key takeaways

**Split the cost and dature looks very different from a naïve "full-cycle" number.** The three
pieces are independent: import (~153 ms, once per process), fresh build+load (~1.6–3.5 ms, only
in function mode), and warm reuse (~100 µs, or ~1.2 µs cached).

**Import is reasonable — comparable to pydantic-settings, lighter on RAM.** ~153 ms vs ~109 ms,
and 11.5 MiB vs 12.1 MiB. (A naïve measurement inside a fat venv reports ~2× higher for everyone —
`site-packages` size inflates import time; always measure imports in a clean venv.)

**Don't use function mode in a hot path.** Rebuilding the adaptix retort every call costs
~1.6–3.5 ms and ~0.6–0.8 MiB — the heaviest column here. Build the loader once (decorator or
`Loader` reuse) and it drops to ~100 µs / ~11 KiB; cache it and it's ~1.2 µs / ~1 KiB. Function
mode is for scripts and one-shot tools, not per-request loading.

**pydantic-settings leads on fresh build+load, but dature wins the steady state.** On a cold
build pydantic-settings is faster and lighter (though its memory is understated — Rust core
invisible to `tracemalloc`). Reused, dature is slightly faster and about half the memory, and
cached it's ~90× faster than either. For a long-running service — build once, load many — that
steady state is what matters.
