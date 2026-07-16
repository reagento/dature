"""Build+load scenario tables shared by bench_speed and bench_memory.

Kept in its own module with **no heavy imports** on purpose: bench_memory's RSS section spawns
a subprocess per row, and on macOS a child spawned from a parent that has already eagerly built
adaptix loaders / loaded pydantic_core (as ``examples_warm`` does at import) can crash. Importing
only these plain data tables keeps that parent light, so the RSS children run cleanly.

Each entry is ``(display label, examples.<function name>)``; order = display order.
"""

# (label, examples function name) per table
SOURCES: dict[str, list[tuple[str, str]]] = {
    "ENV  (os.environ → typed dataclass)": [
        ("dature (func)", "dature_env"),
        ("dature (decorator, cache_engine=False, default)", "dature_env_dec"),
        ("dature (decorator, cache_engine=True)", "dature_env_dec_warm"),
        ("pydantic-settings", "pydantic_env"),
        ("python-decouple", "decouple_env"),
        ("dynaconf", "dynaconf_env"),
    ],
    "ENV file (.env → typed dataclass)": [
        ("dature (func)", "dature_dotenv"),
        ("dature (decorator)", "dature_dotenv_dec"),
        ("pydantic-settings", "pydantic_dotenv"),
        ("python-decouple", "decouple_dotenv"),
        ("dynaconf", "dynaconf_dotenv"),
    ],
    "JSON file (→ typed dataclass)": [
        ("dature (func)", "dature_json"),
        ("dature (decorator)", "dature_json_dec"),
        ("pydantic-settings", "pydantic_json"),
        ("dynaconf", "dynaconf_json"),
    ],
    "TOML file (→ typed dataclass)": [
        ("dature (func)", "dature_toml"),
        ("dature (decorator)", "dature_toml_dec"),
        ("pydantic-settings", "pydantic_toml"),
        ("dynaconf", "dynaconf_toml"),
    ],
    "YAML file (→ typed dataclass / DictConfig)": [
        ("dature (func)", "dature_yaml"),
        ("dature (decorator)", "dature_yaml_dec"),
        ("pydantic-settings", "pydantic_yaml"),
        ("dynaconf", "dynaconf_yaml"),
        ("hydra (DictConfig, not typed)", "hydra_yaml"),
    ],
}

EXPERIMENTS: dict[str, list[tuple[str, str]]] = {
    "Nested model, 5 levels deep (ENV source)": [
        ("dature (func)", "dature_nested"),
        ("dature (decorator)", "dature_nested_dec"),
        ("pydantic-settings", "pydantic_nested"),
    ],
    "Three models loaded at once (ENV source)": [
        ("dature (func)", "dature_multi_model"),
        ("dature (decorator)", "dature_multi_model_dec"),
        ("pydantic-settings", "pydantic_multi_model"),
        ("dynaconf", "dynaconf_multi_model"),
    ],
}
