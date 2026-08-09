"""Tests for hiding dature-internal frames from DatureError/DatureErrorGroup tracebacks."""

import traceback
from dataclasses import dataclass
from pathlib import Path

import pytest

import dature
from dature.errors import DatureConfigError, DatureError, FieldLoadError

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


def _frame_names(exc: Exception) -> list[str]:
    return [frame.name for frame in traceback.extract_tb(exc.__traceback__)]


class TestTracebackHidesInternalFrames:
    """Frames inside src/dature/ must not appear in a dature error's traceback."""

    @pytest.mark.parametrize(
        ("exc_factory", "expected_type"),
        [
            pytest.param(
                lambda: dature.load(
                    dature.Yaml12Source(file=_FIXTURES_DIR / "missing_field.yaml"),
                    schema=_SimpleConfig,
                ),
                DatureConfigError,
                id="missing_field",
            ),
            pytest.param(
                lambda: dature.load(
                    dature.Yaml12Source(file=_FIXTURES_DIR / "does_not_exist.yaml"),
                    schema=_SimpleConfig,
                ),
                DatureConfigError,
                id="file_not_found_wrapped",
            ),
            pytest.param(
                lambda: dature.load(
                    dature.Yaml12Source(file=_FIXTURES_DIR / "broken.yaml"),
                    schema=_SimpleConfig,
                ),
                DatureConfigError,
                id="scanner_error_wrapped",
            ),
            pytest.param(
                lambda: dature.load(
                    dature.Yaml12Source(file=_FIXTURES_DIR / "validation_post_init_invalid.yaml"),
                    schema=_PostInitConfig,
                ),
                DatureConfigError,
                id="value_error_post_init_wrapped",
            ),
        ],
    )
    def test_no_internal_frames_but_caller_frame_kept(
        self,
        exc_factory: object,
        expected_type: type[Exception],
    ) -> None:
        exc: Exception | None = None

        try:
            exc_factory()  # type: ignore[operator]
        except Exception as e:  # noqa: BLE001
            exc = e

        assert exc is not None, "Expected exception was not raised"
        assert isinstance(exc, expected_type)

        frame_names = _frame_names(exc)

        assert "test_no_internal_frames_but_caller_frame_kept" in frame_names
        for name in frame_names:
            assert name not in {"load", "_do_load", "_prepare_for_load"}


class TestTracebackRebuildIsNonDestructive:
    def test_real_traceback_keeps_full_length_after_read(self) -> None:
        try:
            dature.load(
                dature.Yaml12Source(file=_FIXTURES_DIR / "missing_field.yaml"),
                schema=_SimpleConfig,
            )
        except DatureConfigError as exc:
            real_traceback_slot = vars(BaseException)["__traceback__"]

            trimmed_length = len(traceback.extract_tb(exc.__traceback__))
            real_length = len(traceback.extract_tb(real_traceback_slot.__get__(exc)))

            assert trimmed_length < real_length


class TestTracebackKeepsUserFramesForUserRaisedErrors:
    def test_error_raised_directly_by_user_code_keeps_all_frames(self) -> None:
        def _outer() -> None:
            _inner()

        def _inner() -> None:
            msg = "user-raised error"
            raise DatureError(msg)

        with pytest.raises(DatureError) as exc_info:
            _outer()

        frame_names = _frame_names(exc_info.value)

        assert "_outer" in frame_names
        assert "_inner" in frame_names


class TestExceptionGroupContractPreserved:
    def test_except_star_and_exceptions_attribute_still_work(self, tmp_path: Path) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost"}')

        matched: ExceptionGroup[FieldLoadError] | None = None
        try:
            dature.load(dature.JsonSource(file=json_file), schema=_SimpleConfig)
        except* FieldLoadError as eg:
            matched = eg

        assert matched is not None
        assert len(matched.exceptions) == 1


class TestTracebackSetterAcceptsNone:
    def test_setting_traceback_to_none_does_not_raise(self) -> None:
        exc = DatureError("boom")

        with pytest.raises(DatureError) as exc_info:
            raise exc

        exc_info.value.__traceback__ = None

        assert exc_info.value.__traceback__ is None


class TestForeignExceptionWrappedCleanly:
    """Regression guard for the `exc.__traceback__ = None` line kept in loader.py."""

    def test_wrapped_file_not_found_has_no_nested_traceback_header(self) -> None:
        try:
            dature.load(
                dature.Yaml12Source(file=_FIXTURES_DIR / "does_not_exist.yaml"),
                schema=_SimpleConfig,
            )
        except DatureConfigError as exc:
            rendered = "".join(traceback.format_exception(exc))

            # The group itself prints one "Exception Group Traceback (most recent call last):"
            # header (which contains this substring). A second, nested plain "Traceback (most
            # recent call last):" would mean the wrapped FileNotFoundError leaked its own
            # internal traceback into the sub-exception block.
            assert rendered.count("Traceback (most recent call last):") == 1
