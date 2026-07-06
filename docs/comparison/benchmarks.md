# Performance Benchmarks

Performance comparison of dature against pydantic-settings, python-decouple, dynaconf, and hydra.

## Methodology

- Machine: Apple M3, Python 3.13.13
- Harness: `timeit.repeat(number=500, repeat=5)`, mean ± stddev in µs per call
- Config schema: 8 fields (`host: str`, `port: int`, `debug: bool`, `max_connections: int`, `timeout: float`, `db_name: str`, `workers: int`, `log_level: str`)
- Library versions: pydantic-settings 2.14.2 · python-decouple 3.8 · dynaconf 3.2.13 · hydra-core 1.3.3

Run yourself:

```bash
uv sync --group benchmarks
uv run --group benchmarks python benchmarks/run_all.py
```

---

## dature: function mode vs decorator mode

dature exposes two usage patterns with different performance profiles:

**Function mode** — a throwaway `Loader` is created on every call:
```python
config = dature.load(source, schema=BenchConfig)  # Loader + load on every call
```

**Decorator mode** — `Loader` is created once at class-decoration time (import), subsequent calls only run `loader.load()`:
```python
@dature.load(source)
@dataclass
class Config:
    ...

config = Config()  # only loader.load() — Loader already built
```

Or equivalently: `Config = dature.load(source)(BenchConfig)` at module level.

The benchmarks below show both modes. Each section also includes a **startup cost** table measuring `dature.load(source)(BenchConfig)` — the one-time decoration step that happens at import in a real application.

---

## ENV loading (os.environ → typed dataclass)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 5.1 µs | ±0.1 | baseline |
| dature (decorator, hot) | 91.8 µs | ±2.1 | 17.9× |
| pydantic-settings | 103.9 µs | ±1.4 | 20.2× |
| dature (func mode) | 1 488.4 µs | ±41.4 | 289.9× |
| dynaconf | 4 805.0 µs | ±47.0 | 936.0× |

| dature decorator startup (one-time) | Mean | ±Std |
|-------------------------------------|-----:|-----:|
| `dature.load(source)(Config)` | 189.9 µs | ±4.5 |

In decorator mode dature matches pydantic-settings on the hot path. Function mode is 16× slower because it reconstructs the `Loader` (schema introspection + adaptix retort setup) on every call.

---

## JSON file loading (file → typed dataclass)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 222.7 µs | ±6.4 | baseline |
| dature (decorator, hot) | 440.3 µs | ±25.4 | 2.0× |
| dature (func mode) | 2 866.4 µs | ±512.2 | 12.9× |
| dynaconf | 5 347.3 µs | ±105.4 | 24.0× |

| dature decorator startup (one-time) | Mean | ±Std |
|-------------------------------------|-----:|-----:|
| `dature.load(source)(Config)` | 196.0 µs | ±5.8 |

*python-decouple: no JSON file support. hydra: YAML only.*

---

## TOML file loading (file → typed dataclass)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 270.3 µs | ±12.6 | baseline |
| dature (decorator, hot) | 497.9 µs | ±17.1 | 1.8× |
| dature (func mode) | 2 985.4 µs | ±291.2 | 11.0× |
| dynaconf | 5 447.3 µs | ±95.3 | 20.2× |

| dature decorator startup (one-time) | Mean | ±Std |
|-------------------------------------|-----:|-----:|
| `dature.load(source)(Config)` | 207.8 µs | ±3.6 |

*python-decouple: no TOML file support. hydra: YAML only.*

---

## YAML file loading (file → typed dataclass)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 413.4 µs | ±15.1 | baseline |
| dature (decorator, hot) | 1 103.5 µs | ±425.5 | 2.7× |
| dature (func mode) | 2 874.6 µs | ±455.1 | 7.0× |
| dynaconf | 5 769.8 µs | ±114.7 | 14.0× |
| hydra (DictConfig, not typed) | 18 107.3 µs | ±488.9 | 43.8× |

| dature decorator startup (one-time) | Mean | ±Std |
|-------------------------------------|-----:|-----:|
| `dature.load(source)(Config)` | 201.4 µs | ±3.3 |

*python-decouple: no YAML file support. hydra result is `OmegaConf DictConfig` — not a typed dataclass — and includes mandatory `GlobalHydra` singleton reset overhead on every call.*

---

## .env file loading (file → typed dataclass)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 7.0 µs | ±0.3 | baseline |
| dature (decorator, hot) | 501.5 µs | ±30.1 | 71.7× |
| pydantic-settings | 527.1 µs | ±27.8 | 75.4× |
| dature (func mode) | 2 469.3 µs | ±227.7 | 353.3× |
| dynaconf | 11 171.5 µs | ±134.8 | 1 598.3× |

| dature decorator startup (one-time) | Mean | ±Std |
|-------------------------------------|-----:|-----:|
| `dature.load(source)(Config)` | 209.4 µs | ±0.7 |

*hydra: no .env file support.*

python-decouple wins because it caches the parsed file internally and returns values with minimal overhead per call.

---

## Multi-source merge (JSON defaults + ENV overrides → typed dataclass)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| pydantic-settings | 270.6 µs | ±11.4 | baseline |
| dature (decorator, hot) | 534.9 µs | ±79.4 | 2.0× |
| dature (func mode) | 3 341.1 µs | ±172.9 | 12.3× |
| dynaconf | 4 674.2 µs | ±1 289.5 | 17.3× |

| dature decorator startup (one-time) | Mean | ±Std |
|-------------------------------------|-----:|-----:|
| `dature.load(source1, source2)(Config)` | 245.8 µs | ±2.5 |

*python-decouple: not designed for multi-source merging. hydra: YAML only, no native ENV merge.*

---

## Caching (dature decorator cache modes)

### Per-call cost (no caching)

| Library | Mean | ±Std | vs fastest |
|---------|-----:|-----:|-----:|
| python-decouple | 5.0 µs | ±0.1 | baseline |
| dature (decorator, no cache) | 95.9 µs | ±1.8 | 19.3× |
| pydantic-settings | 107.3 µs | ±1.6 | 21.6× |
| dature (func mode) | 1 523.1 µs | ±60.5 | 306.3× |
| dynaconf | 4 915.0 µs | ±87.4 | 988.4× |

| dature decorator startup (one-time) | Mean | ±Std |
|-------------------------------------|-----:|-----:|
| `dature.load(source)(Config)` | 186.8 µs | ±1.3 |

### With caching enabled

| Mode | Mean | ±Std |
|------|-----:|-----:|
| `dature.load(source, cache=False)(Config)` — no cache | 95.9 µs | ±1.8 |
| `dature.load(source, cache=True)(Config)` — eternal | 10.0 µs | ±1.6 |
| `dature.load(source, cache=timedelta(minutes=5))(Config)` — TTL | 10.4 µs | ±1.2 |

With caching enabled, per-call cost drops ~10× — the cache returns the stored result after a TTL check, skipping env-var reads and type coercion entirely. The TTL mode (`cache=timedelta`) adds automatic expiry without any extra code.

---

## Key takeaways

**Decorator mode changes the comparison entirely.** Function mode creates a `Loader` (schema introspection + adaptix retort setup) on every call — ~2 400 µs overhead regardless of source type. Decorator mode pays that cost once at import (~200 µs) and only runs `loader.load()` per call, bringing dature to within 2× of pydantic-settings on file sources and matching it on ENV.

**Startup cost is ~200 µs and happens once.** `dature.load(source)(Config)` takes ~190–250 µs to decorate a class. In a real application this happens once at module import time and is never paid again.

**Function mode is the right choice for scripts and one-shot tools.** No upfront cost, no module-level objects — just call `dature.load(source, schema=Config)` and get a result. Decorator mode is for services and long-running processes where the class is constructed many times.

**pydantic-settings leads on file formats in both modes.** Its Rust-backed parser is consistently 2× faster than dature on JSON/TOML/YAML file reads. The gap is the file parsing layer, not schema machinery.

**hydra is unsuitable for tight loops.** The `GlobalHydra` singleton forces a reset on every isolated call, adding ~14 ms overhead. In production, hydra is initialized once at process start — but that makes it a different usage pattern, not a benchmarkable per-call library.
