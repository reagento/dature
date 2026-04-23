"""Tests for config_paths utilities."""

import sys
from pathlib import Path

import pytest

from dature.config_paths import find_config, get_system_config_dirs


class TestGetSystemConfigDirs:
    """Tests for get_system_config_dirs generator."""

    @pytest.mark.parametrize(
        ("platform", "home", "env", "expected"),
        [
            pytest.param(
                "linux",
                "/home/user",
                {},
                [
                    "/home/user/.config",
                    "/etc",
                    "/etc/xdg",
                ],
                id="linux-defaults",
            ),
            pytest.param(
                "linux",
                "/home/user",
                {"XDG_CONFIG_HOME": "/custom/config"},
                [
                    "/custom/config",
                    "/etc",
                    "/etc/xdg",
                ],
                id="linux-xdg-home-set",
            ),
            pytest.param(
                "linux",
                "/home/user",
                {"XDG_CONFIG_DIRS": "/etc/xdg:/usr/local/etc/xdg"},
                [
                    "/home/user/.config",
                    "/etc",
                    "/etc/xdg",
                    "/usr/local/etc/xdg",
                ],
                id="linux-xdg-dirs-set",
            ),
            pytest.param(
                "darwin",
                "/Users/user",
                {},
                [
                    "/Users/user/Library/Application Support",
                    "/Users/user/.config",
                    "/etc",
                    "/etc/xdg",
                ],
                id="darwin-defaults",
            ),
            pytest.param(
                "win32",
                "/home/user",
                {"APPDATA": r"C:\Users\Test\AppData\Roaming"},
                [r"C:\Users\Test\AppData\Roaming"],
                id="win32-appdata-set",
            ),
            pytest.param(
                "win32",
                "/home/user",
                {},
                [],
                id="win32-appdata-unset",
            ),
        ],
    )
    def test_dirs_by_platform(
        self,
        platform: str,
        home: str,
        env: dict[str, str],
        expected: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "platform", platform)
        monkeypatch.setattr(Path, "home", lambda: Path(home))
        for key in ("APPDATA", "XDG_CONFIG_HOME", "XDG_CONFIG_DIRS"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        assert list(get_system_config_dirs()) == [Path(p) for p in expected]


class TestFindConfig:
    """Tests for find_config function."""

    def test_returns_first_existing(self, tmp_path: Path) -> None:
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

    def test_uses_default_dirs_when_none_passed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("XDG_CONFIG_DIRS", raising=False)

        config_dir = tmp_path / ".config"
        config_dir.mkdir()
        config_file = config_dir / "app.yaml"
        config_file.write_text("found: true")

        assert find_config("app.yaml") == config_file
