"""Pytest configuration and shared fixtures."""

import builtins
import sys
import time
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
import time_machine

from dature.config import _ConfigProxy


@pytest.fixture
def time_control() -> Generator[time_machine.Traveller, None, None]:
    """Freeze wall-clock via ``time_machine`` AND bridge ``time.monotonic`` /
    ``time.perf_counter`` to it so that ``traveller.shift(seconds)`` advances
    both clocks consistently. Returns the underlying ``time_machine`` traveller.
    """
    mono_start = 1_000_000.0

    with time_machine.travel("2024-01-01 00:00:00", tick=False) as traveller:
        wall_start = time.time()

        def fake_monotonic() -> float:
            return mono_start + (time.time() - wall_start)

        def fake_monotonic_ns() -> int:
            return int(fake_monotonic() * 1e9)

        with (
            patch("time.monotonic", side_effect=fake_monotonic),
            patch("time.monotonic_ns", side_effect=fake_monotonic_ns),
            patch("time.perf_counter", side_effect=fake_monotonic),
        ):
            yield traveller


@pytest.fixture
def examples_dir() -> Path:
    """Return path to examples directory."""
    return Path(__file__).parent.parent / "examples"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


# ENV fixtures
@pytest.fixture
def prefixed_env_file(fixtures_dir: Path) -> Path:
    """Path to .env file with APP_ prefix."""
    return fixtures_dir / "prefixed.env"


@pytest.fixture
def custom_separator_env_file(fixtures_dir: Path) -> Path:
    """Path to .env file with custom separator (dot instead of __)."""
    return fixtures_dir / "custom_separator.env"


@pytest.fixture
def all_types_env_file(examples_dir: Path) -> Path:
    """Path to all_types.env file."""
    return examples_dir / "sources" / "all_types.env"


# YAML fixtures
@pytest.fixture
def yaml_config_with_env_vars_file(fixtures_dir: Path) -> Path:
    """Path to YAML config file with environment variable substitution."""
    return fixtures_dir / "config_with_env_vars.yaml"


@pytest.fixture
def prefixed_yaml_file(fixtures_dir: Path) -> Path:
    """Path to YAML file with prefix."""
    return fixtures_dir / "prefixed.yaml"


@pytest.fixture
def all_types_yaml11_file(examples_dir: Path) -> Path:
    """Path to all_types YAML 1.1 file."""
    return examples_dir / "sources" / "all_types_yaml11.yaml"


@pytest.fixture
def all_types_yaml12_file(examples_dir: Path) -> Path:
    """Path to all_types YAML 1.2 file."""
    return examples_dir / "sources" / "all_types_yaml12.yaml"


# JSON fixtures
@pytest.fixture
def prefixed_json_file(fixtures_dir: Path) -> Path:
    """Path to JSON file with prefix."""
    return fixtures_dir / "prefixed.json"


@pytest.fixture
def all_types_json_file(examples_dir: Path) -> Path:
    """Path to all_types.json file."""
    return examples_dir / "sources" / "all_types.json"


# JSON5 fixtures
@pytest.fixture
def prefixed_json5_file(fixtures_dir: Path) -> Path:
    """Path to JSON5 file with prefix."""
    return fixtures_dir / "prefixed.json5"


@pytest.fixture
def all_types_json5_file(examples_dir: Path) -> Path:
    """Path to all_types.json5 file."""
    return examples_dir / "sources" / "all_types.json5"


# TOML fixtures
@pytest.fixture
def prefixed_toml_file(fixtures_dir: Path) -> Path:
    """Path to TOML file with prefix."""
    return fixtures_dir / "prefixed.toml"


@pytest.fixture
def all_types_toml10_file(examples_dir: Path) -> Path:
    """Path to all_types TOML 1.0 file."""
    return examples_dir / "sources" / "all_types_toml10.toml"


@pytest.fixture
def all_types_toml11_file(examples_dir: Path) -> Path:
    """Path to all_types TOML 1.1 file."""
    return examples_dir / "sources" / "all_types_toml11.toml"


@pytest.fixture
def array_of_tables_toml_file(fixtures_dir: Path) -> Path:
    return fixtures_dir / "array_of_tables.toml"


@pytest.fixture
def array_of_tables_error_first_toml_file(fixtures_dir: Path) -> Path:
    return fixtures_dir / "array_of_tables_error_first.toml"


@pytest.fixture
def array_of_tables_error_last_toml_file(fixtures_dir: Path) -> Path:
    return fixtures_dir / "array_of_tables_error_last.toml"


# INI fixtures
@pytest.fixture
def ini_sections_file(fixtures_dir: Path) -> Path:
    """Path to INI file with multiple sections and DEFAULT inheritance."""
    return fixtures_dir / "sections.ini"


@pytest.fixture
def prefixed_ini_file(fixtures_dir: Path) -> Path:
    """Path to INI file with prefix."""
    return fixtures_dir / "prefixed.ini"


@pytest.fixture
def all_types_ini_file(examples_dir: Path) -> Path:
    """Path to all_types.ini file."""
    return examples_dir / "sources" / "all_types.ini"


# Docker secrets fixtures
@pytest.fixture
def all_types_docker_secrets_dir(examples_dir: Path) -> Path:
    """Path to all_types_docker_secrets directory."""
    return examples_dir / "sources" / "all_types_docker_secrets"


# Vault fixtures
@pytest.fixture
def all_types_vault_file(examples_dir: Path) -> Path:
    """Path to all_types_vault.json file."""
    return examples_dir / "sources" / "all_types_vault.json"


# Consul fixtures
@pytest.fixture
def all_types_consul_kv_file(examples_dir: Path) -> Path:
    """Path to all_types_consul_kv.json file."""
    return examples_dir / "sources" / "all_types_consul_kv.json"


# etcd fixtures
@pytest.fixture
def all_types_etcd_kv_file(examples_dir: Path) -> Path:
    """Path to all_types_etcd_kv.json file."""
    return examples_dir / "sources" / "all_types_etcd_kv.json"


@pytest.fixture
def _clean_dature_modules() -> Generator[None]:
    removed: dict[str, object] = {}
    for key in list(sys.modules):
        if key.startswith("dature."):
            removed[key] = sys.modules.pop(key)
    yield
    sys.modules.update(removed)


@pytest.fixture
def block_import(_clean_dature_modules: None) -> Callable[[str], AbstractContextManager[None]]:
    real_import = builtins.__import__

    def _block(module_name: str) -> AbstractContextManager[None]:
        @contextmanager
        def _ctx() -> Generator[None]:
            # Drop any cached entry so ``import <module_name>`` actually goes through __import__
            # — otherwise a previously-imported module short-circuits the block.
            removed = {
                key: sys.modules.pop(key)
                for key in list(sys.modules)
                if key == module_name or key.startswith(module_name + ".")
            }

            def _blocker(name: str, *args: object, **kwargs: object) -> object:
                if name == module_name or name.startswith(module_name + "."):
                    msg = f"No module named '{module_name}'"
                    raise ImportError(msg)
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=_blocker):
                try:
                    yield
                finally:
                    sys.modules.update(removed)

        return _ctx()

    return _block


@pytest.fixture
def _reset_config() -> Generator[None]:
    _ConfigProxy.set_instance(None)
    yield
    _ConfigProxy.set_instance(None)
