# Performance Benchmarks

Comparison of dature against pydantic-settings, python-decouple, dynaconf, and hydra across two dimensions: **speed** (µs per call) and **memory** (peak KiB allocated per call).

## Methodology

**Speed** — `timeit.repeat(number=500, repeat=5)`, mean ± stddev in µs per call.  
**Memory** — `tracemalloc` peak allocation per call, mean of 20 runs with 5 warmup calls. Tracks Python heap only; pydantic-settings uses a Rust extension (`pydantic_core`) whose internal allocations are invisible here, so its memory numbers are understated.

Machine: Apple M3, Python 3.13.13.  
Schema: 8 fields — `host: str`, `port: int`, `debug: bool`, `max_connections: int`, `timeout: float`, `db_name: str`, `workers: int`, `log_level: str`.  
Library versions: pydantic-settings 2.14.2 · python-decouple 3.8 · dynaconf 3.2.13 · hydra-core 1.3.3.

Run yourself:

```bash
uv sync --group benchmarks
uv run --group benchmarks python benchmarks/bench_speed.py
uv run --group benchmarks python benchmarks/bench_memory.py
```

---

## dature: function mode vs decorator mode

dature has two usage patterns with very different performance profiles:

**Function mode** — a throwaway `Loader` is created on every call:
```python
config = dature.load(source, schema=Config)
```

**Decorator mode** — `Loader` is built once at class-decoration time (import); each call only runs `loader.load()`:
```python
Config = dature.load(source)(BenchConfig)  # at module level
config = Config()                           # hot path
```

The decorator pays a one-time **startup cost** of ~190–210 µs and ~62 KiB at import time, then never again. Function mode avoids that upfront cost — useful for scripts and one-shot tools — but reconstructs the full `Loader` (schema introspection + adaptix retort setup, ~750 KiB overhead) on every call.

The benchmark tables below show both modes. "decorator, hot" is the steady-state after startup.

---

## ENV loading

`os.environ` → typed dataclass, 8 fields with `BENCH_` prefix.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 5.1 µs | ±0.1 | baseline |
| dature (decorator, hot) | 91.8 µs | ±2.1 | 17.9× |
| pydantic-settings | 103.9 µs | ±1.4 | 20.2× |
| dature (func mode) | 1 488.4 µs | ±41.4 | 289.9× |
| dynaconf | 4 805.0 µs | ±47.0 | 936.0× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| python-decouple | 2.8 KiB | baseline |
| dature (decorator, hot) | 7.6 KiB | 2.7× |
| pydantic-settings | 16.6 KiB | 5.9× |
| dynaconf | 138.5 KiB | 49.0× |
| dature (func mode) | 794.8 KiB | 281.0× |

python-decouple leads on both dimensions because it parses env vars with minimal abstraction and caches its internal state.

---

## JSON file loading

JSON file → typed dataclass.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 222.7 µs | ±6.4 | baseline |
| dature (decorator, hot) | 440.3 µs | ±25.4 | 2.0× |
| dature (func mode) | 2 866.4 µs | ±512.2 | 12.9× |
| dynaconf | 5 347.3 µs | ±105.4 | 24.0× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| dature (decorator, hot) | 11.1 KiB | baseline |
| pydantic-settings | 22.4 KiB | 2.0× |
| dynaconf | 141.6 KiB | 12.8× |
| dature (func mode) | 786.6 KiB | 70.9× |

*python-decouple: no JSON file support. hydra: YAML only.*

dature (decorator) is the lightest on memory (2× less than pydantic-settings) while pydantic-settings leads on speed, likely due to its Rust-backed JSON parser.

---

## TOML file loading

TOML file → typed dataclass.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 270.3 µs | ±12.6 | baseline |
| dature (decorator, hot) | 497.9 µs | ±17.1 | 1.8× |
| dature (func mode) | 2 985.4 µs | ±291.2 | 11.0× |
| dynaconf | 5 447.3 µs | ±95.3 | 20.2× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| dature (decorator, hot) | 10.6 KiB | baseline |
| pydantic-settings | 22.3 KiB | 2.1× |
| dynaconf | 140.8 KiB | 13.3× |
| dature (func mode) | 794.5 KiB | 75.0× |

*python-decouple: no TOML file support. hydra: YAML only.*

Same pattern as JSON: pydantic-settings wins on speed, dature (decorator) is the lightest on memory.

---

## YAML file loading

YAML file → typed dataclass (hydra returns `OmegaConf DictConfig`, not a typed dataclass).

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 413.4 µs | ±15.1 | baseline |
| dature (decorator, hot) | 1 103.5 µs | ±425.5 | 2.7× |
| dature (func mode) | 2 874.6 µs | ±455.1 | 7.0× |
| dynaconf | 5 769.8 µs | ±114.7 | 14.0× |
| hydra (DictConfig, not typed) | 18 107.3 µs | ±488.9 | 43.8× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| dature (decorator, hot) | 32.4 KiB | baseline |
| pydantic-settings | 35.5 KiB | 1.1× |
| dynaconf | 155.5 KiB | 4.8× |
| hydra (DictConfig, not typed) | 502.5 KiB | 15.5× |
| dature (func mode) | 803.6 KiB | 24.8× |

*python-decouple: no YAML file support.*

YAML parsing is more expensive than JSON/TOML across all libraries. Hydra's `GlobalHydra` singleton forces a reset on every call (+14 ms, +470 KiB), making it unsuitable for per-call benchmarking; in production it initializes once at startup.

---

## .env file loading

`.env` file → typed dataclass.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 7.0 µs | ±0.3 | baseline |
| dature (decorator, hot) | 501.5 µs | ±30.1 | 71.7× |
| pydantic-settings | 527.1 µs | ±27.8 | 75.4× |
| dature (func mode) | 2 469.3 µs | ±227.7 | 353.3× |
| dynaconf | 11 171.5 µs | ±134.8 | 1 598.3× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| python-decouple | 2.2 KiB | baseline |
| dature (decorator, hot) | 18.5 KiB | 8.3× |
| pydantic-settings | 35.5 KiB | 15.9× |
| dynaconf | 224.6 KiB | 100.7× |
| dature (func mode) | 796.4 KiB | 357.1× |

*hydra: no .env file support.*

python-decouple wins by a wide margin on both dimensions: it caches the parsed file internally and returns values with minimal per-call overhead.

---

## Multi-source merge

JSON file (base defaults) + ENV vars (overrides) → typed dataclass.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 270.6 µs | ±11.4 | baseline |
| dature (decorator, hot) | 534.9 µs | ±79.4 | 2.0× |
| dature (func mode) | 3 341.1 µs | ±172.9 | 12.3× |
| dynaconf | 4 674.2 µs | ±1 289.5 | 17.3× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| dature (decorator, hot) | 14.6 KiB | baseline |
| pydantic-settings | 23.0 KiB | 1.6× |
| dynaconf | 88.6 KiB | 6.1× |
| dature (func mode) | 804.9 KiB | 55.1× |

*python-decouple: not designed for multi-source merging. hydra: YAML only, no native ENV merge.*

---

## Caching

Caching is a separate concern from source type. All caching benchmarks use `EnvSource` as the baseline.

### Speed (µs per call) — no caching

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 5.0 µs | ±0.1 | baseline |
| dature (decorator, no cache) | 95.9 µs | ±1.8 | 19.3× |
| pydantic-settings | 107.3 µs | ±1.6 | 21.6× |
| dature (func mode) | 1 523.1 µs | ±60.5 | 306.3× |
| dynaconf | 4 915.0 µs | ±87.4 | 988.4× |

### Speed (µs per call) — with caching

| Mode | Mean | ±Std |
|------|-----:|-----:|
| `dature.load(source, cache=False)(Config)` — no cache | 95.9 µs | ±1.8 |
| `dature.load(source, cache=True)(Config)` — eternal | 10.0 µs | ±1.6 |
| `dature.load(source, cache=timedelta(minutes=5))(Config)` — TTL | 10.4 µs | ±1.2 |

With caching enabled, dature drops to ~10 µs — a ~10× improvement over the uncached decorator. The TTL mode (`cache=timedelta`) adds automatic expiry with no extra code.

### Memory (peak KiB per call) — no caching

| Library | Peak |
|---------|-----:|
| dature (decorator, no cache) | 7.6 KiB |

### Memory (peak KiB per call) — with caching

| Mode | Peak |
|------|-----:|
| pydantic-settings + `@lru_cache` | 0.0 KiB |
| python-decouple + `@lru_cache` | 0.0 KiB |
| dynaconf + `@lru_cache` | 0.0 KiB |
| `dature.load(source, cache=True)(Config)` — eternal | 3.4 KiB |
| `dature.load(source, cache=timedelta(minutes=5))(Config)` — TTL | 3.4 KiB |

`@lru_cache` returns the exact same object reference on every call — zero allocation. dature's built-in cache creates a fresh dataclass instance each call (3.4 KiB), which matters when callers mutate the config or need isolated copies. The trade-off: `@lru_cache` has no TTL; dature's `cache=timedelta` expires automatically.

---

## Key takeaways

**The decorator/function choice matters more than the library choice.** Function mode allocates ~750–800 KiB per call and takes ~1.5–3.5 ms regardless of source type — the cost of rebuilding the `Loader` on every call. Decorator mode pays ~190–210 µs and ~62 KiB once at import, then each call costs <1 ms and <35 KiB. The right question is not "which library is fastest?" but "am I using the right mode?"

**On ENV (the most common source), dature (decorator) matches pydantic-settings.** Both sit at ~90–110 µs and 7–17 KiB per call. python-decouple is 20× faster and 3× lighter, but it doesn't do schema-driven type coercion — you cast fields manually.

**On file sources, the roles flip between speed and memory.** pydantic-settings is 2× faster than dature on JSON/TOML/YAML (its Rust parser), but dature (decorator) allocates 2× less. For memory-sensitive services with many workers, dature's file-source footprint is smaller.

**dynaconf is consistently the heaviest option.** 90–225 KiB per call and 5–20× slower than dature (decorator) across every source type. Its flexibility comes at a significant per-call cost.

**Caching is worth it when config doesn't change per request.** Dature's `cache=True` brings per-call cost from ~96 µs to ~10 µs (10×). The `cache=timedelta` variant adds TTL expiry — something `@lru_cache` wrappers can't do without extra code.
