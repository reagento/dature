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

**Speed** (`bench_speed.py`) — in-process, `timeit.repeat(number=500, repeat=5)`. The library
is already imported (a warmup call warms `sys.modules`), so these numbers exclude import and
capture only the per-call work. Every library re-declares its model class each call, so it's
apples-to-apples.

**Memory** (`bench_memory.py`) — two different tools, each matched to what it measures honestly:

- **Build + load → retained RSS.** How much resident memory *stays* after building N objects and
  keeping them alive (process RSS growth ÷ N, measured in a fresh subprocess per row). We use RSS
  rather than `tracemalloc` because `tracemalloc` only sees the Python heap: pydantic-settings does
  most of its schema work in a Rust extension (`pydantic_core`) that `tracemalloc` cannot see, which
  understates it ~20× and makes the comparison meaningless. RSS counts native allocations too, so
  it is a fair cross-library number. (A `tracemalloc` *peak* for a single dature build reads a few
  hundred KiB, but that is transient code-generation scratch that is freed immediately — not
  retained footprint.)
- **Warm reuse → `tracemalloc` peak per call.** Here nothing new stays resident (the loader is
  pre-built and reused), so an RSS delta would read ~0; `tracemalloc` correctly captures the
  transient per-call allocation churn.

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
| adaptix (dature's engine) | 112.4 ms | baseline | 8.3 MiB | baseline |
| pydantic-settings | 114.1 ms | 1.0× | 12.1 MiB | 1.5× |
| dature | 161.8 ms | 1.4× | 11.5 MiB | 1.4× |

dature imports in ~162 ms and ~11.5 MiB — about 1.4× pydantic-settings on time, and slightly
**lighter** on memory. Most of dature's import is adaptix (its type engine, ~112 ms); dature's
own code adds ~50 ms. This is a one-time cost paid once per process, not per config load.

---

## 2. Build + load (per fresh load, import excluded)

One full cycle with nothing reused. Rows ordered by speed. Memory is **retained RSS per build**
(see Methodology) — the resident cost that actually stays, counting native/Rust allocations, not
the transient `tracemalloc` peak.

### ENV (`os.environ` → typed dataclass)

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| python-decouple | 151 µs | baseline | 11.3 KiB | baseline |
| pydantic-settings | 298 µs | 2.0× | 27.4 KiB | 2.4× |
| dature (func) | 975 µs | 6.5× | 38.8 KiB | 3.4× |
| dature (decorator) | 1.2 ms | 7.9× | 99.1 KiB | 8.8× |
| dynaconf | 10.0 ms | 66.2× | 12.6 KiB | 1.1× |

### ENV file (`.env` → typed dataclass)

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| python-decouple | 638 µs | baseline | 11.3 KiB | baseline |
| pydantic-settings | 1.4 ms | 2.3× | 28.1 KiB | 2.5× |
| dature (func) | 2.1 ms | 3.4× | 38.9 KiB | 3.4× |
| dature (decorator) | 2.4 ms | 3.7× | 100.4 KiB | 8.9× |
| dynaconf | 17.6 ms | 27.6× | 13.3 KiB | 1.2× |

### JSON file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 609 µs | baseline | 28.2 KiB | 2.4× |
| dature (func) | 2.2 ms | 3.5× | 22.8 KiB | 1.9× |
| dature (decorator) | 2.3 ms | 3.7× | 101.4 KiB | 8.5× |
| dynaconf | 5.9 ms | 9.6× | 11.9 KiB | baseline |

*python-decouple: no JSON file support.*

### TOML file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 547 µs | baseline | 28.1 KiB | 2.4× |
| dature (decorator) | 2.2 ms | 4.1× | 103.2 KiB | 8.8× |
| dature (func) | 2.7 ms | 4.9× | 23.1 KiB | 2.0× |
| dynaconf | 5.6 ms | 10.3× | 11.7 KiB | baseline |

*python-decouple: no TOML file support.*

### YAML file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 894 µs | baseline | 28.3 KiB | 2.3× |
| dature (func) | 2.8 ms | 3.1× | 23.0 KiB | 1.9× |
| dature (decorator) | 2.8 ms | 3.2× | 100.1 KiB | 8.1× |
| dynaconf | 6.0 ms | 6.7× | 12.3 KiB | baseline |
| hydra (DictConfig, not typed) | 18.6 ms | 20.8× | — | — |

*python-decouple: no YAML file support. hydra returns an `OmegaConf DictConfig`, not a typed
dataclass; its RSS is not measured (GlobalHydra is a process singleton, so it can't be built in
a tight loop).*

### Nested model, 5 levels deep (ENV source)

Five dataclasses nested five levels deep (`Level1.inner → … → Level5`), from `__`-joined env keys.

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 676 µs | baseline | 70.7 KiB | baseline |
| dature (func) | 2.2 ms | 3.3× | 106.6 KiB | 1.5× |
| dature (decorator) | 2.4 ms | 3.6× | 166.0 KiB | 2.3× |

*python-decouple / hydra: no schema-driven nested model from ENV.*

### Three models loaded at once (ENV source)

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 598 µs | baseline | 45.5 KiB | 4.7× |
| dature (func) | 1.8 ms | 3.0× | 70.0 KiB | 7.2× |
| dature (decorator) | 2.3 ms | 3.8× | 248.5 KiB | 25.7× |
| dynaconf | 13.9 ms | 23.3× | 9.7 KiB | baseline |

On a fresh build dature is ~3–5× slower than pydantic-settings on speed, because it generates and
compiles an adaptix loader (Python codegen) while pydantic builds its schema in Rust. On
**memory** dature (func) retains ~23–39 KiB per build — the string-value sources (ENV, ENV file)
sit slightly higher than the file-format sources (JSON, TOML, YAML, ~23 KiB). dature (decorator)
retains more (~100 KiB) because a decorated class **keeps its `Loader` and compiled retort alive**
for the class lifetime — a one-time cost per class, not per load, and exactly what makes warm
reuse cheap (see below).

---

## 3. Warm reuse

Hot path once the loader is built at module level, and with caching. The steady state of a
long-running service.

Both dature (loader built once) and pydantic-settings (schema cached on the class) are measured
re-loading over their pre-built object.

| Mode | Speed | vs | Memory | vs |
|------|------:|---:|-------:|---:|
| dature — decorator, hot,  `cache=True` (eternal) | 1.0 µs | baseline | 1.0 KiB | baseline |
| dature — decorator, hot, `cache=timedelta(...)` (TTL) | 1.0 µs | 1.0× | 1.1 KiB | 1.1× |
| dature — decorator, hot, no cache | 59.2 µs | 59.6× | 10.5 KiB | 10.3× |
| dature — `Loader` reuse, no cache | 55.7 µs | 56.1× | 10.2 KiB | 10.0× |
| pydantic-settings — reuse | 113.2 µs | 113.9× | 20.6 KiB | 20.1× |
| dature — function mode, fixed schema, no reuse | 156 µs | 157× | 14.0 KiB | 13.7× |

In steady state the ranking flips versus build+load: dature (loader reused) is **faster**
than pydantic-settings reused (~56 µs vs ~113 µs) and about half the memory (10.2 vs 20.6 KiB).
Caching drops dature to ~1 µs / ~1 KiB — ~110× faster than either. `cache=timedelta` adds
automatic TTL expiry a plain `@lru_cache` wrapper can't do.

The last row is the honest counter-example: function mode with the schema declared once but a
**throwaway `Loader` on every call** (~156 µs). Even though the schema never changes, each fresh
`Loader` pays for its own setup; reuse comes from keeping the `Loader` alive (decorator or explicit
`Loader`), which drops it to ~56 µs, and caching drops it to ~1 µs.

---

## Key takeaways

**Split the cost and dature looks very different from a native "full-cycle" number.** The three
pieces are independent: import (~162 ms, once per process), fresh build+load (~1.2–3.0 ms, only
in function mode), and warm reuse (~74 µs, or ~1 µs cached).

**Import is reasonable — comparable to pydantic-settings, lighter on RAM.** ~162 ms vs ~114 ms,
and 11.5 MiB vs 12.1 MiB. (A native measurement inside a fat venv reports ~2× higher for everyone —
`site-packages` size inflates import time; always measure imports in a clean venv.)

**Don't use function mode in a hot path.** Building and compiling the adaptix loader on every
call costs ~1.2–3.0 ms. Even with a fixed schema, a throwaway `Loader` per call costs ~156 µs
because each fresh loader discards its setup — build the loader once (decorator or `Loader`
reuse) and it drops to ~56 µs; cache it and it's ~1 µs. Function mode is for scripts and one-shot
tools, not per-request loading.

**dature's memory is comparable-to-lighter than pydantic.** Measured as retained RSS (a fair,
native-aware metric), dature (func) holds ~22 KiB per build vs pydantic's ~28 KiB. `tracemalloc`
would mislead here — it sees dature's transient Python codegen but is blind to pydantic's Rust
core, which is why we report RSS (see Methodology). dature (decorator) retains more (~100 KiB)
only because it keeps the compiled loader alive for reuse.

**pydantic-settings leads on cold build speed, but dature wins the steady state.** On a cold
build pydantic is faster (Rust codegen vs Python); memory is comparable-to-better. Reused, dature
is faster (~56 µs vs ~113 µs) and about half the memory, and cached it's ~110× faster than either.
For a long-running service — build once, load many — that steady state is what matters.
