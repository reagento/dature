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

By default the decorator (like the function) does **not** retain its compiled engine —
`cache_engine` defaults to `False` (see [Caching](../advanced/caching.md)). The ENV table below
contrasts that default against the explicit `cache_engine=True` opt-in, which is what pays for
the cheap warm reuse in section 3.

### ENV (`os.environ` → typed dataclass)

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| python-decouple | 147 µs | baseline | 11.2 KiB | baseline |
| pydantic-settings | 287 µs | 2.0× | 27.4 KiB | 2.4× |
| dature (func) | 1.1 ms | 7.6× | 22.3 KiB | 2.0× |
| dature (decorator, `cache_engine=False`, default) | 1.1 ms | 7.6× | 30.4 KiB | 2.7× |
| dature (decorator, `cache_engine=True`) | 1.1 ms | 7.6× | 100.9 KiB | 9.0× |
| dynaconf | 3.9 ms | 26.3× | 11.8 KiB | 1.1× |

### ENV file (`.env` → typed dataclass)

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| python-decouple | 410 µs | baseline | 11.4 KiB | baseline |
| pydantic-settings | 1.3 ms | 3.1× | 28.0 KiB | 2.5× |
| dature (func) | 2.7 ms | 6.5× | 22.7 KiB | 2.0× |
| dature (decorator) | 2.7 ms | 6.5× | 31.2 KiB | 2.7× |
| dynaconf | 8.5 ms | 20.8× | 12.6 KiB | 1.1× |

### JSON file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 1.0 ms | baseline | 28.3 KiB | 2.5× |
| dature (func) | 2.4 ms | 2.4× | 22.8 KiB | 2.0× |
| dature (decorator) | 2.8 ms | 2.7× | 31.2 KiB | 2.7× |
| dynaconf | 3.8 ms | 3.7× | 11.4 KiB | baseline |

*python-decouple: no JSON file support.*

### TOML file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 709 µs | baseline | 28.1 KiB | 2.4× |
| dature (decorator) | 2.4 ms | 3.4× | 31.0 KiB | 2.7× |
| dature (func) | 2.5 ms | 3.6× | 22.7 KiB | 2.0× |
| dynaconf | 3.2 ms | 4.5× | 11.5 KiB | baseline |

*python-decouple: no TOML file support.*

### YAML file

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 803 µs | baseline | 28.2 KiB | 2.4× |
| dature (func) | 2.6 ms | 3.3× | 22.7 KiB | 1.9× |
| dature (decorator) | 2.7 ms | 3.3× | 31.3 KiB | 2.6× |
| dynaconf | 3.3 ms | 4.1× | 11.9 KiB | baseline |
| hydra (DictConfig, not typed) | 17.5 ms | 21.8× | — | — |

*python-decouple: no YAML file support. hydra returns an `OmegaConf DictConfig`, not a typed
dataclass; its RSS is not measured (GlobalHydra is a process singleton, so it can't be built in
a tight loop).*

### Nested model, 5 levels deep (ENV source)

Five dataclasses nested five levels deep (`Level1.inner → … → Level5`), from `__`-joined env keys.

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 670 µs | baseline | 65.2 KiB | baseline |
| dature (func) | 2.4 ms | 3.6× | 65.2 KiB | baseline |
| dature (decorator) | 2.4 ms | 3.6× | 71.3 KiB | 1.1× |

*python-decouple / hydra: no schema-driven nested model from ENV.*

### Three models loaded at once (ENV source)

| Library | Speed | vs | Memory (RSS) | vs |
|---------|------:|---:|-------------:|---:|
| pydantic-settings | 576 µs | baseline | 45.3 KiB | 4.8× |
| dature (func) | 2.3 ms | 4.0× | 41.6 KiB | 4.4× |
| dature (decorator) | 2.4 ms | 4.1× | 63.8 KiB | 6.7× |
| dynaconf | 7.5 ms | 13.1× | 9.5 KiB | baseline |

On a fresh build dature is a few× slower than pydantic-settings on speed, because it generates
and compiles an adaptix loader (Python codegen) while pydantic builds its schema in Rust. On
**memory**dature (func) retains ~23–39 KiB per build — the string-value sources (ENV, ENV file)
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
| dature — decorator, hot, `cache=True` (default) | 1.0 µs | baseline | 1.0 KiB | baseline |
| dature — decorator, hot, `cache=timedelta(...)` (TTL) | 1.1 µs | 1.1× | 1.1 KiB | baseline |
| dature — `Loader` reuse, `cache_engine=True` | 56.0 µs | 55.3× | 10.2 KiB | 10.0× |
| dature — decorator, hot, `cache_engine=True` | 57.8 µs | 57.1× | 10.6 KiB | 10.3× |
| pydantic-settings — reuse | 119.7 µs | 118.1× | 20.6 KiB | 20.1× |
| dature — decorator, hot, `cache_engine=False` | 889 µs | 876.9× | 424.5 KiB | 413.5× |
| dature — function mode, fixed schema, no reuse | 920 µs | 907.7× | 424.7 KiB | 413.8× |

In steady state, opting into `cache_engine=True` **flips** the ranking versus build+load: dature
(`Loader` reuse) is **faster** than pydantic-settings reused (~56 µs vs ~120 µs) and about half
the memory (10.2 vs 20.6 KiB). Caching (`cache=True`/`cache=timedelta`) drops dature to ~1 µs /
~1 KiB — over 100× faster than either. `cache=timedelta` adds automatic TTL expiry a plain
`@lru_cache` wrapper can't do.

The last two rows are the honest counter-example: with `cache_engine` left at its **default**
(`False`), nothing about the compiled engine survives a call, so both the decorator (with
`cache=False`) and function mode pay full recompilation every time — ~889–920 µs and ~425 KiB of
transient churn per call. That's the trade-off `cache_engine` makes explicit: the default keeps
the decorator's *retained* footprint low (section 2) at the cost of the hot path; set
`cache_engine=True` (or leave the default `cache=True`, which caches the *result* and never needs
to recompile after the first call) to get the fast path back.

---

## Key takeaways

**Split the cost and dature looks very different from a native "full-cycle" number.** The three
pieces are independent: import (~162 ms, once per process), fresh build+load (~1.1–2.8 ms, only
in function mode), and warm reuse (~57 µs with `cache_engine=True`, ~1 µs cached).

**Import is reasonable — comparable to pydantic-settings, lighter on RAM.** ~162 ms vs ~114 ms,
and 11.5 MiB vs 12.1 MiB. (A native measurement inside a fat venv reports ~2× higher for everyone —
`site-packages` size inflates import time; always measure imports in a clean venv.)

**Don't use function mode in a hot path.** Building and compiling the adaptix loader on every
call costs ~1.1–2.8 ms. Even with a fixed schema, a throwaway `Loader` per call costs ~920 µs
because each fresh loader discards its setup — build the loader once *and* opt into
`cache_engine=True` (decorator or `Loader` reuse) and it drops to ~56–58 µs; cache the result
(`cache=True`, the default) and it's ~1 µs. Function mode is for scripts and one-shot tools, not
per-request loading.

**`cache_engine` controls whether the compiled engine is retained — default off.** At the default
`cache_engine=False`, dature (decorator) retains only ~30 KiB per build, close to dature (func)
and pydantic-settings, because nothing about the compiled loader survives past the call that
built it. Opting into `cache_engine=True` trades that back for ~100 KiB of retained memory in
exchange for a ~15× faster hot path (~58 µs vs ~890 µs) — the right call for a long-running
service, the wrong call for a short-lived script. `cache` (which defaults to `True`) is a
separate knob: it caches the *loaded result*, so after the first call the compiled engine is
never needed again regardless of `cache_engine` — which is exactly why the default pairs
`cache=True` with `cache_engine=False`.

**dature's memory is comparable-to-lighter than pydantic.** Measured as retained RSS (a fair,
native-aware metric), dature (func) holds ~22 KiB per build vs pydantic's ~27–28 KiB.
`tracemalloc` would mislead here — it sees dature's transient Python codegen but is blind to
pydantic's Rust core, which is why we report RSS (see Methodology).

**pydantic-settings leads on cold build speed, but dature wins the steady state.** On a cold
build pydantic is faster (Rust codegen vs Python); memory is comparable-to-better. Reused with
`cache_engine=True`, dature is faster (~56 µs vs ~120 µs) and about half the memory, and cached
it's over 100× faster than either. For a long-running service — build once, load many — that
steady state is what matters.
