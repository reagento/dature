"""Unit tests for dature.loading.load_logging — debug-logging helpers."""

import logging
from dataclasses import dataclass

import pytest

from dature.config import MaskingConfig
from dature.loading.load_logging import (
    log_field_origins,
    log_merge_step,
    log_single_source_load,
)
from dature.loading.merge_runtime import MergeStepEvent
from dature.report_types import FieldOrigin
from dature.sources.base import Source
from dature.type_aliases import JSONValue

_NO_MASKING = MaskingConfig(masking_mode="none")
_SECRETS_ONLY = MaskingConfig(masking_mode="secrets_only")


@dataclass(kw_only=True)
class _MockSource(Source):
    format_name: str = "mock"
    location_label: str = "MOCK"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data


def _event(
    *,
    step_idx: int = 0,
    source_data: JSONValue = None,
    before: JSONValue = None,
    after: JSONValue = None,
) -> MergeStepEvent:
    return MergeStepEvent(
        step_idx=step_idx,
        source=_MockSource(),
        source_data=source_data or {},
        before=before or {},
        after=after or {},
    )


def _messages(caplog: pytest.LogCaptureFixture, dataclass_name: str) -> list[str]:
    prefix = f"[{dataclass_name}]"
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith(prefix)]


class TestLogMergeStep:
    def test_emits_debug_records(self, caplog: pytest.LogCaptureFixture) -> None:
        event = _event(
            step_idx=1,
            source_data={"host": "remote"},
            before={"host": "local"},
            after={"host": "remote"},
        )

        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_merge_step(
                event=event,
                dataclass_name="Config",
                strategy_label="last_wins",
                secret_paths=frozenset(),
                masking=_NO_MASKING,
            )

        assert _messages(caplog, "Config") == [
            "[Config] Merge step 1 (strategy=last_wins): added=[], overwritten=['host']",
            "[Config] State after step 1: {'host': 'remote'}",
        ]

    def test_secret_paths_masked_in_after_state(self, caplog: pytest.LogCaptureFixture) -> None:
        event = _event(
            step_idx=0,
            after={"password": "super-secret"},
        )

        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_merge_step(
                event=event,
                dataclass_name="Config",
                strategy_label="last_wins",
                secret_paths=frozenset({"password"}),
                masking=_SECRETS_ONLY,
            )

        assert _messages(caplog, "Config") == [
            "[Config] Merge step 0 (strategy=last_wins): added=[], overwritten=[]",
            "[Config] State after step 0: {'password': '<REDACTED>'}",
        ]

    def test_empty_before_and_source_still_emits(self, caplog: pytest.LogCaptureFixture) -> None:
        event = _event(step_idx=0, source_data={}, before={}, after={"x": 1})

        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_merge_step(
                event=event,
                dataclass_name="Config",
                strategy_label="last_wins",
                secret_paths=frozenset(),
                masking=_NO_MASKING,
            )

        assert _messages(caplog, "Config") == [
            "[Config] Merge step 0 (strategy=last_wins): added=[], overwritten=[]",
            "[Config] State after step 0: {'x': 1}",
        ]


class TestLogFieldOrigins:
    def test_one_record_per_origin(self, caplog: pytest.LogCaptureFixture) -> None:
        origins = (
            FieldOrigin(key="host", value="localhost", source_index=0, source_file=None, source_loader_type="mock"),
            FieldOrigin(key="port", value=3000, source_index=0, source_file=None, source_loader_type="mock"),
        )

        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_field_origins(dataclass_name="Config", field_origins=origins, masking=_NO_MASKING)

        assert _messages(caplog, "Config") == [
            "[Config] Field 'host' = 'localhost'  <-- source 0 (None)",
            "[Config] Field 'port' = 3000  <-- source 0 (None)",
        ]

    def test_secret_key_is_masked(self, caplog: pytest.LogCaptureFixture) -> None:
        origins = (
            FieldOrigin(key="password", value="hunter2", source_index=0, source_file=None, source_loader_type="mock"),
        )

        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_field_origins(
                dataclass_name="Config",
                field_origins=origins,
                secret_paths=frozenset({"password"}),
                masking=_NO_MASKING,
            )

        assert _messages(caplog, "Config") == [
            "[Config] Field 'password' = '<REDACTED>'  <-- source 0 (None)",
        ]

    def test_non_secret_value_appears_in_log(self, caplog: pytest.LogCaptureFixture) -> None:
        origins = (
            FieldOrigin(key="host", value="myserver", source_index=0, source_file=None, source_loader_type="mock"),
        )

        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_field_origins(dataclass_name="Config", field_origins=origins, masking=_NO_MASKING)

        assert _messages(caplog, "Config") == [
            "[Config] Field 'host' = 'myserver'  <-- source 0 (None)",
        ]

    def test_empty_origins_emits_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_field_origins(dataclass_name="Config", field_origins=(), masking=_NO_MASKING)

        assert _messages(caplog, "Config") == []

    @pytest.mark.parametrize(
        "origin_key",
        ["secret-key", "secretKey", "SECRET_KEY"],
        ids=["kebab", "lower-camel", "upper-snake"],
    )
    def test_masks_styled_origin_key(self, caplog: pytest.LogCaptureFixture, origin_key: str) -> None:
        origins = (
            FieldOrigin(key=origin_key, value="hunter2", source_index=0, source_file=None, source_loader_type="mock"),
        )

        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_field_origins(
                dataclass_name="Config",
                field_origins=origins,
                secret_paths=frozenset({"secret_key"}),
                masking=_SECRETS_ONLY,
            )

        assert _messages(caplog, "Config") == [
            f"[Config] Field '{origin_key}' = '<REDACTED>'  <-- source 0 (None)",
        ]


class TestLogSingleSourceLoad:
    def test_emits_loader_and_data_lines(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_single_source_load(
                dataclass_name="Config",
                loader_type="yaml",
                file_path="/etc/config.yaml",
                data={"host": "localhost"},
                masking=_NO_MASKING,
            )

        assert _messages(caplog, "Config") == [
            "[Config] Single-source load: loader=yaml, file=/etc/config.yaml",
            "[Config] Loaded data: {'host': 'localhost'}",
        ]

    def test_secret_paths_masked_in_data(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_single_source_load(
                dataclass_name="Config",
                loader_type="env",
                file_path=".env",
                data={"api_key": "top-secret"},
                secret_paths=frozenset({"api_key"}),
                masking=_SECRETS_ONLY,
            )

        assert _messages(caplog, "Config") == [
            "[Config] Single-source load: loader=env, file=.env",
            "[Config] Loaded data: {'api_key': '<REDACTED>'}",
        ]

    def test_non_secret_data_appears_in_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="dature"):
            log_single_source_load(
                dataclass_name="Config",
                loader_type="json",
                file_path="config.json",
                data={"host": "public-server"},
                masking=_NO_MASKING,
            )

        assert _messages(caplog, "Config") == [
            "[Config] Single-source load: loader=json, file=config.json",
            "[Config] Loaded data: {'host': 'public-server'}",
        ]
