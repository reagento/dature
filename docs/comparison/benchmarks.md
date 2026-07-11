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
| pydantic-settings | 286 µs | 1.9× | 27.5 KiB | 2.4× |
| dature (func) | 1.2 ms | 7.9× | 22.7 KiB | 2.0× |
| dature (decorator) | 1.3 ms | 8.4× | 103.4 KiB | 9.2× |
| dynaconf | 10.0 ms | 66.5× | 12.7 KiB | 1.1× |

### ENV file (`.env` → typed dataclass)

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| python-decouple | 727 µs | baseline | 11.3 KiB | baseline |
| pydantic-settings | 1.5 ms | 2.0× | 28.0 KiB | 2.5× |
| dature (decorator) | 2.4 ms | 3.3× | 104.6 KiB | 9.3× |
| dature (func) | 2.5 ms | 3.5× | 22.8 KiB | 2.0× |
| dynaconf | 17.8 ms | 24.4× | 13.2 KiB | 1.2× |

### JSON file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 527 µs | baseline | 28.2 KiB | 2.4× |
| dature (decorator) | 2.6 ms | 5.0× | 101.1 KiB | 8.6× |
| dature (func) | 2.8 ms | 5.3× | 22.5 KiB | 1.9× |
| dynaconf | 5.8 ms | 11.0× | 11.7 KiB | baseline |

*python-decouple: no JSON file support.*

### TOML file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 931 µs | baseline | 28.2 KiB | 2.4× |
| dature (decorator) | 2.5 ms | 2.7× | 103.1 KiB | 8.7× |
| dature (func) | 2.5 ms | 2.7× | 22.5 KiB | 1.9× |
| dynaconf | 5.8 ms | 6.2× | 11.9 KiB | baseline |

*python-decouple: no TOML file support.*

### YAML file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 1.0 ms | baseline | 28.2 KiB | 2.3× |
| dature (func) | 2.9 ms | 2.9× | 22.4 KiB | 1.8× |
| dature (decorator) | 3.0 ms | 3.0× | 99.7 KiB | 8.1× |
| dynaconf | 6.2 ms | 6.2× | 12.4 KiB | baseline |
| hydra (DictConfig, not typed) | 18.4 ms | 18.3× | — | — |

*python-decouple: no YAML file support. hydra returns an `OmegaConf DictConfig`, not a typed
dataclass; its RSS is not measured (GlobalHydra is a process singleton, so it can't be built in
a tight loop).*

### Nested model, 5 levels deep (ENV source)

Five dataclasses nested five levels deep (`Level1.inner → … → Level5`), from `__`-joined env keys.

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 701 µs | baseline | 70.4 KiB | 1.1× |
| dature (decorator) | 2.6 ms | 3.7× | 170.1 KiB | 2.7× |
| dature (func) | 2.7 ms | 3.9× | 63.8 KiB | baseline |

*python-decouple / hydra: no schema-driven nested model from ENV.*

### Three models loaded at once (ENV source)

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 582 µs | baseline | 45.3 KiB | 4.7× |
| dature (decorator) | 2.5 ms | 4.4× | 261.7 KiB | 27.0× |
| dature (func) | 2.6 ms | 4.5× | 41.4 KiB | 4.3× |
| dynaconf | 14.1 ms | 24.2× | 9.7 KiB | baseline |

On a fresh build dature is ~2–8× slower than pydantic-settings on speed, because it generates and
compiles an adaptix loader (Python codegen) while pydantic builds its schema in Rust. The fast/rich
`debug_trail` split (see Key takeaways) shaved ~25% off this cold cost. On **memory** dature is now
comparable-to-lighter: dature (func) retains ~22 KiB per build — *below* pydantic's ~28 KiB — not
the ~20× a `tracemalloc` peak would suggest (that peak is transient codegen scratch, freed
immediately). dature (decorator) retains more (~100 KiB) because a decorated class **keeps its
`Loader` and compiled retort alive** for the class lifetime — a one-time cost per class, not per
load, and exactly what makes warm reuse cheap (see below).

---

## 3. Warm reuse

Hot path once the loader is built at module level, and with caching. The steady state of a
long-running service.

Both dature (loader built once) and pydantic-settings (schema cached on the class) are measured
re-loading over their pre-built object.

| Mode | Speed | vs | Memory | vs |
|------|------:|---:|-------:|---:|
| dature — `cache=True` (eternal) | 1.0 µs | baseline | 1.0 KiB | baseline |
| dature — `cache=timedelta(...)` (TTL) | 1.1 µs | 1.1× | 1.1 KiB | 1.1× |
| dature — `Loader` reuse | 74.0 µs | 72.1× | 10.2 KiB | 10.2× |
| dature — decorator, hot | 76.8 µs | 74.7× | 10.5 KiB | 10.5× |
| pydantic-settings — reuse | 113.8 µs | 110.8× | 20.3 KiB | 20.3× |
| dature — function mode, fixed schema, no reuse | 1.1 ms | 1027× | 427.8 KiB | 428× |

In steady state the ranking flips versus build+load: dature (loader reused) is **faster**
than pydantic-settings reused (~74 µs vs ~114 µs) and about half the memory (10.2 vs 20.3 KiB).
Caching drops dature to ~1 µs / ~1 KiB — ~110× faster than either. `cache=timedelta` adds
automatic TTL expiry a plain `@lru_cache` wrapper can't do.

The last row is the honest counter-example: function mode with the schema declared once but a
**throwaway `Loader` on every call** stays at ~1.1 ms / ~428 KiB. Reuse comes from keeping the
`Loader` alive (decorator or an explicit `Loader`), not from a stable schema alone — each fresh
`Loader` rebuilds and recompiles its retort.

---

## Key takeaways

**Split the cost and dature looks very different from a naïve "full-cycle" number.** The three
pieces are independent: import (~162 ms, once per process), fresh build+load (~1.2–3.0 ms, only
in function mode), and warm reuse (~74 µs, or ~1 µs cached).

**Import is reasonable — comparable to pydantic-settings, lighter on RAM.** ~162 ms vs ~114 ms,
and 11.5 MiB vs 12.1 MiB. (A naïve measurement inside a fat venv reports ~2× higher for everyone —
`site-packages` size inflates import time; always measure imports in a clean venv.)

**Don't use function mode in a hot path.** Building and compiling the adaptix loader every call
costs ~1.2–3.0 ms, and a throwaway `Loader` pays it even when the schema is fixed (see the last
Warm-reuse row). Build the loader once (decorator or `Loader` reuse) and it drops to ~74 µs; cache
it and it's ~1 µs. Function mode is for scripts and one-shot tools, not per-request loading.

**Cold build was cut ~25% by a fast/rich `debug_trail` split.** adaptix's default `DebugTrail.ALL`
wraps every field in error-path-tracking code — that's what gives dature its field-path errors,
but it also inflates the generated loader (slower to compile, heavier). dature now loads the happy
path through a trail-free (`DebugTrail.DISABLE`) retort and only *replays* the load through the
rich trailed retort when it actually fails — so a valid config is ~25% cheaper to build and lighter
in memory, while a broken config still gets the full aggregated, field-located error.

**dature's memory is comparable-to-lighter than pydantic — the old "800 KiB vs 40 KiB" was a
measurement artifact.** That gap came from `tracemalloc`, which sees dature's transient Python
codegen but is blind to pydantic's Rust core. Measured as retained RSS (a fair, native-aware
metric), dature (func) holds ~22 KiB per build vs pydantic's ~28 KiB. dature (decorator) retains
more (~100 KiB) only because it keeps the compiled loader alive for reuse.

**pydantic-settings leads on cold build speed, but dature wins the steady state.** On a cold
build pydantic is faster (Rust codegen vs Python); memory is comparable-to-better. Reused, dature
is faster (~74 µs vs ~114 µs) and about half the memory, and cached it's ~110× faster than either.
For a long-running service — build once, load many — that steady state is what matters.
