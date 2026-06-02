"""Tests for sys.excepthook patching in dature.errors.excepthook."""

import sys
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from unittest.mock import MagicMock

import pytest

import dature
from dature.errors.excepthook import _dature_excepthook

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@dataclass
class _SimpleConfig:
    host: str
    port: int


@dataclass
class _PostInitConfig:
    host: str
    port: int

    def __post_init__(self) -> None:
        if self.port > 65535:
            msg = f"port must be between 1 and 65535, got {self.port}"
            raise ValueError(msg)


def test_excepthook_is_installed() -> None:
    assert sys.excepthook is _dature_excepthook


class TestDatureExcepthookSuppressesTraceback:
    """Exceptions that originate from dature.load() must print without traceback."""

    @pytest.mark.parametrize(
        ("exc_factory", "expected_fragment"),
        [
            pytest.param(
                lambda: dature.load(
                    dature.Yaml12Source(file=_FIXTURES_DIR / "missing_field.yaml"),
                    schema=_SimpleConfig,
                ),
                "DatureConfigError",
                id="dature_config_error_missing_field",
            ),
            pytest.param(
                lambda: dature.load(
                    dature.Yaml12Source(file=_FIXTURES_DIR / "does_not_exist.yaml"),
                    schema=_SimpleConfig,
                ),
                "FileNotFoundError",
                id="file_not_found_wrapped",
            ),
            pytest.param(
                lambda: dature.load(
                    dature.Yaml12Source(file=_FIXTURES_DIR / "broken.yaml"),
                    schema=_SimpleConfig,
                ),
                "ScannerError",
                id="scanner_error_wrapped",
            ),
            pytest.param(
                lambda: dature.load(
                    dature.Yaml12Source(file=_FIXTURES_DIR / "validation_post_init_invalid.yaml"),
                    schema=_PostInitConfig,
                ),
                "ValueError",
                id="value_error_post_init_wrapped",
            ),
        ],
    )
    def test_no_traceback_in_output(
        self,
        exc_factory: object,
        expected_fragment: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        exc: BaseException | None = None
        try:
            exc_factory()  # type: ignore[operator]
        except BaseException as e:  # noqa: BLE001
            exc = e

        assert exc is not None, "Expected exception was not raised"

        _dature_excepthook(type(exc), exc, exc.__traceback__)

        err = capsys.readouterr().err
        assert "Traceback (most recent call last):" not in err
        assert 'File "' not in err
        assert expected_fragment in err


def _raise_plain_value_error() -> None:
    msg = "plain user error"
    raise ValueError(msg)


class TestDatureExcepthookDelegatesNonDature:
    """Exceptions not from dature must be forwarded to the previous excepthook."""

    def test_non_dature_exc_delegates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_prev = MagicMock()
        monkeypatch.setattr("dature.errors.excepthook._previous_excepthook", mock_prev)

        try:
            _raise_plain_value_error()
        except ValueError as exc:
            tb: TracebackType | None = exc.__traceback__
            _dature_excepthook(type(exc), exc, tb)
            mock_prev.assert_called_once_with(ValueError, exc, tb)
