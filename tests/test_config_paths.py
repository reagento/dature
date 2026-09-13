"""Tests for config_paths utilities."""

import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from dature.config_paths import find_config


class TestFindConfig:
    """Tests for find_config function."""

    def test_returns_none_for_none_dirs(self) -> None:
        assert find_config("app.yaml", None) is None

    def test_finds_first_existing_with_path_entries(self, tmp_path: Path) -> None:
        first_dir = tmp_path / "first"
        first_dir.mkdir()
        first_config = first_dir / "config.yaml"
        first_config.write_text("test: first")

        second_dir = tmp_path / "second"
        second_dir.mkdir()
        second_config = second_dir / "config.yaml"
        second_config.write_text("test: second")

        assert find_config("config.yaml", (first_dir, second_dir)) == first_config

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        assert find_config("nonexistent.yaml", (tmp_path / "nonexistent",)) is None

    def test_accepts_str_entries(self, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").write_text("a: 1")

        assert find_config("config.yaml", (str(tmp_path),)) == tmp_path / "config.yaml"

    def test_expands_env_var(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "config.yaml").write_text("a: 1")
        monkeypatch.setenv("DATURE_TEST_DIR", str(tmp_path))

        assert find_config("config.yaml", ("$DATURE_TEST_DIR",)) == tmp_path / "config.yaml"

    def test_expands_tilde(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_dir = tmp_path / "conf"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("a: 1")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        assert find_config("config.yaml", ("~/conf",)) == config_dir / "config.yaml"

    @pytest.mark.parametrize(
        ("var_set", "expected_subdir"),
        [
            pytest.param(True, "from_var", id="var-set"),
            pytest.param(False, "fallback", id="var-unset"),
        ],
    )
    def test_fallback_syntax(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        var_set: bool,
        expected_subdir: str,
    ) -> None:
        var_dir = tmp_path / "from_var"
        var_dir.mkdir()
        fallback_dir = tmp_path / "fallback"
        fallback_dir.mkdir()
        (var_dir / "config.yaml").write_text("source: var")
        (fallback_dir / "config.yaml").write_text("source: fallback")

        monkeypatch.delenv("DATURE_TEST_DIR", raising=False)
        if var_set:
            monkeypatch.setenv("DATURE_TEST_DIR", str(var_dir))
        monkeypatch.setenv("DATURE_TEST_FALLBACK", str(fallback_dir))

        result = find_config(
            "config.yaml",
            ("${DATURE_TEST_DIR:-$DATURE_TEST_FALLBACK}",),
        )

        assert result == tmp_path / expected_subdir / "config.yaml"

    def test_skips_undefined_env_var_with_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        (tmp_path / "config.yaml").write_text("a: 1")
        monkeypatch.delenv("DATURE_UNDEFINED_XYZ", raising=False)

        with caplog.at_level(logging.WARNING, logger="dature"):
            result = find_config(
                "config.yaml",
                ("$DATURE_UNDEFINED_XYZ/nowhere", str(tmp_path)),
            )

        assert result == tmp_path / "config.yaml"
        assert any(
            "DATURE_UNDEFINED_XYZ" in record.message and "config_dirs" in record.message for record in caplog.records
        )

    def test_skips_undefined_fallback_var_with_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Regression: a missing var inside a ${VAR:-fallback} fallback used to raise
        # EnvVarExpandError out of find_config instead of the documented warn-and-skip
        # behavior — the default config_dirs on linux/darwin is exactly this shape
        # ("${XDG_CONFIG_HOME:-$HOME/.config}"), so an unset HOME would have crashed.
        (tmp_path / "config.yaml").write_text("a: 1")
        monkeypatch.delenv("DATURE_UNDEFINED_XYZ", raising=False)
        monkeypatch.delenv("DATURE_ALSO_UNDEFINED_XYZ", raising=False)

        with caplog.at_level(logging.WARNING, logger="dature"):
            result = find_config(
                "config.yaml",
                ("${DATURE_UNDEFINED_XYZ:-$DATURE_ALSO_UNDEFINED_XYZ}/nowhere", str(tmp_path)),
            )

        assert result == tmp_path / "config.yaml"
        expected_message = (
            "config_dirs: environment variable 'DATURE_ALSO_UNDEFINED_XYZ' is not set; skipping entry "
            "'${DATURE_UNDEFINED_XYZ:-$DATURE_ALSO_UNDEFINED_XYZ}/nowhere'"
        )
        assert [record.getMessage() for record in caplog.records] == [expected_message]

    def test_mapping_selects_by_platform(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        linux_dir = tmp_path / "linux_config"
        linux_dir.mkdir()
        (linux_dir / "config.yaml").write_text("platform: linux")
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        (other_dir / "config.yaml").write_text("platform: other")

        monkeypatch.setattr(sys, "platform", "linux")

        result = find_config(
            "config.yaml",
            {"linux": (linux_dir,), "darwin": (other_dir,)},
        )

        assert result == linux_dir / "config.yaml"

    def test_mapping_missing_platform_returns_empty(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "config.yaml").write_text("a: 1")
        monkeypatch.setattr(sys, "platform", "linux")

        result = find_config("config.yaml", {"darwin": (tmp_path,)})

        assert result is None

    def test_pathsep_split(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        first = tmp_path / "first"
        first.mkdir()
        second = tmp_path / "second"
        second.mkdir()
        (second / "config.yaml").write_text("found: second")

        combined = f"{first}{os.pathsep}{second}"
        monkeypatch.setenv("DATURE_TEST_DIRS", combined)

        assert find_config("config.yaml", ("$DATURE_TEST_DIRS",)) == second / "config.yaml"

    def test_mixed_path_and_str_entries(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "config.yaml").write_text("a: 1")
        monkeypatch.setenv("DATURE_TEST_DIR", str(target_dir))

        entries = (tmp_path / "missing", "$DATURE_TEST_DIR")

        assert find_config("config.yaml", entries) == target_dir / "config.yaml"

    @pytest.mark.parametrize(
        "config_dirs",
        [
            pytest.param(lambda d: d, id="flat-path"),
            pytest.param(str, id="flat-str"),
            pytest.param(lambda d: {"linux": d}, id="mapping-value-path"),
            pytest.param(lambda d: {"linux": str(d)}, id="mapping-value-str"),
        ],
    )
    def test_accepts_single_entry_not_wrapped_in_iterable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        config_dirs: "Callable[[Path], object]",
    ) -> None:
        (tmp_path / "config.yaml").write_text("a: 1")
        monkeypatch.setattr(sys, "platform", "linux")

        result = find_config("config.yaml", config_dirs(tmp_path))

        assert result == tmp_path / "config.yaml"

    def test_single_str_entry_still_splits_on_pathsep(
        self,
        tmp_path: Path,
    ) -> None:
        first = tmp_path / "first"
        first.mkdir()
        second = tmp_path / "second"
        second.mkdir()
        (second / "config.yaml").write_text("found: second")

        combined = f"{first}{os.pathsep}{second}"

        assert find_config("config.yaml", combined) == second / "config.yaml"

    @pytest.mark.parametrize(
        "empty_dirs",
        [
            pytest.param((), id="tuple"),
            pytest.param([], id="list"),
            pytest.param({}, id="mapping"),
        ],
    )
    def test_empty_config_dirs_finds_nothing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        empty_dirs: "tuple[()] | list[object] | dict[str, object]",
    ) -> None:
        monkeypatch.setattr(sys, "platform", "linux")

        result = find_config("config.yaml", empty_dirs)

        assert result is None
