import os
from pathlib import Path

import pytest

from dature import EnvSource, Toml11Source
from dature.errors import EnvVarExpandError
from dature.expansion.env_expand import expand_file_path

SEP = os.sep


class TestExpandFilePath:
    @pytest.mark.parametrize(
        ("file_path", "env_vars", "expected"),
        [
            ("$DATURE_DIR/config.toml", {"DATURE_DIR": "/etc/app"}, "/etc/app/config.toml"),
            ("${DATURE_DIR}/config.toml", {"DATURE_DIR": "/etc/app"}, "/etc/app/config.toml"),
            (
                "config.$DATURE_ENV.toml",
                {"DATURE_ENV": "production"},
                "config.production.toml",
            ),
            (
                "${DATURE_ENV:-staging}.toml",
                {},
                "staging.toml",
            ),
            (
                "$DATURE_DIR/$DATURE_ENV.toml",
                {"DATURE_DIR": "/etc/app", "DATURE_ENV": "prod"},
                "/etc/app/prod.toml",
            ),
            ("/etc/app/config.toml", {}, "/etc/app/config.toml"),
            ("config.toml", {}, "config.toml"),
            (
                "%DATURE_DIR%\\config.toml",
                {"DATURE_DIR": "C:\\Users\\app"},
                "C:\\Users\\app\\config.toml",
            ),
            (
                "%DATURE_DIR%\\config.%DATURE_ENV%.toml",
                {"DATURE_DIR": "C:\\Users\\app", "DATURE_ENV": "prod"},
                "C:\\Users\\app\\config.prod.toml",
            ),
            (
                "${DATURE_DIR}\\config.toml",
                {"DATURE_DIR": "C:\\Users\\app"},
                "C:\\Users\\app\\config.toml",
            ),
        ],
        ids=[
            "dir-dollar",
            "dir-braces",
            "filename-env",
            "filename-fallback",
            "dir-and-filename",
            "no-vars-absolute",
            "no-vars-relative",
            "windows-percent",
            "windows-percent-dir-and-filename",
            "windows-braces-backslash",
        ],
    )
    def test_expansion(
        self,
        monkeypatch: pytest.MonkeyPatch,
        file_path: str,
        env_vars: dict[str, str],
        expected: str,
    ) -> None:
        for key in ("DATURE_DIR", "DATURE_ENV"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        result = expand_file_path(file_path, mode="strict")

        assert result == expected

    @pytest.mark.parametrize(
        "file_path",
        [
            "$DATURE_MISSING/config.toml",
            "config.$DATURE_MISSING.toml",
        ],
        ids=["missing-in-dir", "missing-in-filename"],
    )
    def test_missing_var_strict_raises(self, monkeypatch: pytest.MonkeyPatch, file_path: str) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)

        with pytest.raises(EnvVarExpandError):
            expand_file_path(file_path, mode="strict")

    def test_disabled_no_expansion(self) -> None:
        result = expand_file_path("$HOME/config.toml", mode="disabled")

        assert result == "$HOME/config.toml"


class TestSourceFileExpansion:
    @pytest.mark.parametrize(
        ("file", "env_vars", "expected"),
        [
            ("$DATURE_DIR/config.toml", {"DATURE_DIR": "/etc/app"}, "/etc/app/config.toml"),
            (
                Path("$DATURE_DIR") / "config.toml",
                {"DATURE_DIR": "/etc/app"},
                f"$DATURE_DIR{SEP}config.toml".replace("$DATURE_DIR", "/etc/app"),
            ),
            (
                "config.$DATURE_ENV.toml",
                {"DATURE_ENV": "production"},
                "config.production.toml",
            ),
            ("/etc/app/config.toml", {}, "/etc/app/config.toml"),
            (
                "%DATURE_DIR%\\config.toml",
                {"DATURE_DIR": "C:\\Users\\app"},
                "C:\\Users\\app\\config.toml",
            ),
            (
                Path("$DATURE_DIR") / "config.$DATURE_ENV.toml",
                {"DATURE_DIR": "/etc/app", "DATURE_ENV": "prod"},
                f"$DATURE_DIR{SEP}config.$DATURE_ENV.toml".replace("$DATURE_DIR", "/etc/app").replace(
                    "$DATURE_ENV",
                    "prod",
                ),
            ),
        ],
        ids=["str-dir", "path-dir", "str-filename-env", "no-vars", "str-windows-percent", "path-dir-and-filename"],
    )
    def test_fileexpanded(
        self,
        monkeypatch: pytest.MonkeyPatch,
        file: str | Path,
        env_vars: dict[str, str],
        expected: str,
    ) -> None:
        for key in ("DATURE_DIR", "DATURE_ENV"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        source = Toml11Source(file=file)

        assert source.file == expected

    def test_none_fileunchanged(self) -> None:
        source = EnvSource()

        assert not hasattr(source, "file")

    def test_missing_var_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)

        with pytest.raises(EnvVarExpandError):
            Toml11Source(file="$DATURE_MISSING/config.toml")
