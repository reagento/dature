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

## dature: function mode vs decorator mode vs Loader reuse

dature has three usage patterns with very different performance profiles:

**Function mode** — a throwaway `Loader` is created on every call:
```python
config = dature.load(source, schema=Config)
```

**Decorator mode** — `Loader` is built once at class-decoration time (import); each call only runs `loader.load()`:
```python
Config = dature.load(source)(BenchConfig)  # at module level
config = Config()                           # hot path
```

**Loader reuse** — one `Loader` is created explicitly (same one-time cost as decorator startup), `.load()` called repeatedly:
```python
_loader = Loader(source, schema=Config)  # once, at module level
config = _loader.load()                  # hot path
```

The decorator and Loader reuse patterns pay a one-time **startup cost** of ~63–120 µs and ~7 KiB at import time, then never again. Function mode avoids that upfront cost — useful for scripts and one-shot tools — but reconstructs the full `Loader` (schema introspection + adaptix retort setup, ~790 KiB overhead) on every call.

The benchmark tables below show all three modes. "decorator, hot" and "Loader reuse" are both steady-state after startup — they perform identically.

---

## ENV loading

`os.environ` → typed dataclass, 8 fields with `BENCH_` prefix.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 4.9 µs | ±0.1 | baseline |
| dature (Loader reuse) | 59.7 µs | ±1.6 | 12.2× |
| dature (decorator, hot) | 61.2 µs | ±1.2 | 12.5× |
| pydantic-settings | 104.9 µs | ±1.6 | 21.4× |
| dature (func mode) | 1 325.4 µs | ±20.9 | 270.5× |
| dynaconf | 4 951.7 µs | ±193.2 | 1 010.6× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| python-decouple | 2.8 KiB | baseline |
| dature (Loader reuse) | 5.5 KiB | 1.9× |
| dature (decorator, hot) | 5.9 KiB | 2.1× |
| pydantic-settings | 16.6 KiB | 5.9× |
| dynaconf | 138.5 KiB | 49.0× |
| dature (func mode) | 792.5 KiB | 280.2× |

python-decouple leads on both dimensions because it parses env vars with minimal abstraction and caches its internal state.

---

## JSON file loading

JSON file → typed dataclass.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 245.2 µs | ±18.6 | baseline |
| dature (decorator, hot) | 381.0 µs | ±7.1 | 1.6× |
| dature (Loader reuse) | 446.2 µs | ±19.5 | 1.8× |
| dature (func mode) | 2 719.0 µs | ±314.6 | 11.1× |
| dynaconf | 5 720.7 µs | ±130.5 | 23.3× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| dature (Loader reuse) | 8.6 KiB | baseline |
| dature (decorator, hot) | 8.9 KiB | 1.0× |
| pydantic-settings | 22.4 KiB | 2.6× |
| dynaconf | 141.6 KiB | 16.5× |
| dature (func mode) | 790.1 KiB | 92.0× |

*python-decouple: no JSON file support. hydra: YAML only.*

dature (decorator or Loader reuse) is the lightest on memory (2.6× less than pydantic-settings) while pydantic-settings leads on speed, likely due to its Rust-backed JSON parser.

---

## TOML file loading

TOML file → typed dataclass.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 256.2 µs | ±20.3 | baseline |
| dature (Loader reuse) | 419.9 µs | ±34.2 | 1.6× |
| dature (decorator, hot) | 424.1 µs | ±36.4 | 1.7× |
| dature (func mode) | 3 261.7 µs | ±155.1 | 12.7× |
| dynaconf | 5 629.9 µs | ±151.2 | 22.0× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| dature (Loader reuse) | 7.9 KiB | baseline |
| dature (decorator, hot) | 8.2 KiB | 1.0× |
| pydantic-settings | 22.3 KiB | 2.8× |
| dynaconf | 140.8 KiB | 17.8× |
| dature (func mode) | 792.2 KiB | 100.2× |

*python-decouple: no TOML file support. hydra: YAML only.*

Same pattern as JSON: pydantic-settings wins on speed, dature (decorator or Loader reuse) is the lightest on memory.

---

## YAML file loading

YAML file → typed dataclass (hydra returns `OmegaConf DictConfig`, not a typed dataclass).

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 535.1 µs | ±46.8 | baseline |
| dature (decorator, hot) | 868.8 µs | ±37.2 | 1.6× |
| dature (Loader reuse) | 1 096.5 µs | ±412.4 | 2.0× |
| dature (func mode) | 3 194.6 µs | ±487.2 | 6.0× |
| dynaconf | 6 087.6 µs | ±142.1 | 11.4× |
| hydra (DictConfig, not typed) | 18 974.9 µs | ±509.6 | 35.5× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| dature (Loader reuse) | 28.9 KiB | baseline |
| dature (decorator, hot) | 29.2 KiB | 1.0× |
| pydantic-settings | 35.5 KiB | 1.2× |
| dynaconf | 155.5 KiB | 5.4× |
| hydra (DictConfig, not typed) | 502.5 KiB | 17.4× |
| dature (func mode) | 800.8 KiB | 27.7× |

*python-decouple: no YAML file support.*

YAML parsing is more expensive than JSON/TOML across all libraries. Hydra's `GlobalHydra` singleton forces a reset on every call (+14 ms, +470 KiB), making it unsuitable for per-call benchmarking; in production it initializes once at startup.

---

## .env file loading

`.env` file → typed dataclass.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 8.8 µs | ±2.6 | baseline |
| dature (decorator, hot) | 423.3 µs | ±20.2 | 48.1× |
| dature (Loader reuse) | 430.5 µs | ±33.7 | 48.9× |
| pydantic-settings | 824.5 µs | ±330.1 | 93.7× |
| dature (func mode) | 3 091.5 µs | ±277.1 | 351.3× |
| dynaconf | 12 563.9 µs | ±251.4 | 1 427.7× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| python-decouple | 2.2 KiB | baseline |
| dature (Loader reuse) | 15.5 KiB | 7.1× |
| dature (decorator, hot) | 15.8 KiB | 7.2× |
| pydantic-settings | 35.5 KiB | 16.2× |
| dynaconf | 224.6 KiB | 102.2× |
| dature (func mode) | 794.1 KiB | 361.4× |

*hydra: no .env file support.*

python-decouple wins by a wide margin on both dimensions: it caches the parsed file internally and returns values with minimal per-call overhead.

---

## Multi-source merge

JSON file (base defaults) + ENV vars (overrides) → typed dataclass.

### Speed (µs per call)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 272.0 µs | ±15.0 | baseline |
| dature (decorator, hot) | 485.7 µs | ±33.0 | 1.8× |
| dature (Loader reuse) | 534.9 µs | ±27.7 | 2.0× |
| dature (func mode) | 3 007.1 µs | ±71.1 | 11.1× |
| dynaconf | 4 859.5 µs | ±1 266.2 | 17.9× |

### Memory (peak KiB per call)

| Library | Peak | vs lightest |
|---------|-----:|-----:|
| dature (Loader reuse) | 11.7 KiB | baseline |
| dature (decorator, hot) | 12.1 KiB | 1.0× |
| pydantic-settings | 23.0 KiB | 2.0× |
| dynaconf | 88.6 KiB | 7.6× |
| dature (func mode) | 798.3 KiB | 68.3× |

*python-decouple: not designed for multi-source merging. hydra: YAML only, no native ENV merge.*

---

## Caching

Caching is a separate concern from source type. All caching benchmarks use `EnvSource` as the baseline.

### Speed (µs per call) — no caching

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 4.8 µs | ±0.1 | baseline |
| dature (decorator, no cache) | 68.5 µs | ±1.9 | 14.1× |
| pydantic-settings | 107.0 µs | ±1.1 | 22.1× |
| dature (func mode) | 1 399.0 µs | ±67.4 | 288.7× |
| dynaconf | 4 889.3 µs | ±83.4 | 1 009.1× |

### Speed (µs per call) — with caching

| Mode | Mean | ±Std |
|------|-----:|-----:|
| `dature.load(source, cache=False)(Config)` — no cache | 68.5 µs | ±1.9 |
| `dature.load(source, cache=True)(Config)` — eternal | 1.3 µs | ±1.8 |
| `dature.load(source, cache=timedelta(minutes=5))(Config)` — TTL | 1.3 µs | ±1.4 |

With caching enabled, dature drops to ~1.3 µs — a ~53× improvement over the uncached decorator. The TTL mode (`cache=timedelta`) adds automatic expiry with no extra code.

### Memory (peak KiB per call) — no caching

| Library | Peak |
|---------|-----:|
| dature (decorator, no cache) | 5.9 KiB |

### Memory (peak KiB per call) — with caching

| Mode | Peak |
|------|-----:|
| pydantic-settings + `@lru_cache` | 0.0 KiB |
| python-decouple + `@lru_cache` | 0.0 KiB |
| dynaconf + `@lru_cache` | 0.0 KiB |
| `dature.load(source, cache=True)(Config)` — eternal | 1.0 KiB |
| `dature.load(source, cache=timedelta(minutes=5))(Config)` — TTL | 1.1 KiB |

`@lru_cache` returns the exact same object reference on every call — zero allocation. dature's built-in cache creates a fresh dataclass instance each call (~1.0–1.1 KiB), which matters when callers mutate the config or need isolated copies. The trade-off: `@lru_cache` has no TTL; dature's `cache=timedelta` expires automatically.

---

## Key takeaways

**The decorator/function choice matters more than the library choice.** Function mode allocates ~790–800 KiB per call and takes ~1.4–3.1 ms regardless of source type — the cost of rebuilding the `Loader` on every call (schema introspection + building adaptix retorts from scratch). Decorator mode and Loader reuse pay ~63–120 µs and ~7 KiB once at import, then each call costs <1 ms and <35 KiB. **Loader reuse (`_loader = Loader(source, schema=Config)` at module level, then `_loader.load()` per call) gives identical hot-path performance to decorator mode** — use it when you want explicit control without the class-decoration syntax.

**On ENV (the most common source), dature (decorator or Loader reuse) beats pydantic-settings.** dature sits at ~60–61 µs vs pydantic-settings at ~105 µs; python-decouple at ~5 µs is 12× faster but doesn't do schema-driven type coercion — you cast fields manually.

**On file sources, the roles flip between speed and memory.** pydantic-settings is ~1.6–1.8× faster than dature on JSON/TOML/YAML (its Rust parser), but dature (decorator or Loader reuse) allocates 2.6× less. For memory-sensitive services with many workers, dature's file-source footprint is smaller.

**dynaconf is consistently the heaviest option.** 90–225 KiB per call and 9–22× slower than dature (decorator) across every source type. Its flexibility comes at a significant per-call cost.

**Caching is worth it when config doesn't change per request.** Dature's `cache=True` brings per-call cost from ~69 µs to ~1.3 µs (~53×). The `cache=timedelta` variant adds TTL expiry — something `@lru_cache` wrappers can't do without extra code.
