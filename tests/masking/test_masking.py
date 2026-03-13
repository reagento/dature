from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Literal
from unittest.mock import patch

import pytest

from dature import LoadMetadata, MergeMetadata, get_load_report, load
from dature.errors.exceptions import DatureConfigError
from dature.fields.secret_str import SecretStr
from dature.load_report import FieldOrigin, SourceEntry
from dature.masking.masking import (
    mask_env_line,
    mask_field_origins,
    mask_json_value,
    mask_source_entries,
    mask_value,
)


class TestMaskValue:
    @pytest.mark.parametrize(
        ("input_value", "expected"),
        [
            ("", "*****"),
            ("a", "*****"),
            ("ab", "*****"),
            ("abc", "*****"),
            ("abcd", "*****"),
            ("abcde", "ab*****de"),
            ("abcdef", "ab*****ef"),
            ("abcdefghij", "ab*****ij"),
            ("my_secret_password_123", "my*****23"),
        ],
    )
    def test_mask_value(self, input_value, expected):
        assert mask_value(input_value) == expected


class TestMaskJsonValue:
    def test_mask_secret_string(self):
        data = {"password": "my_secret_123", "host": "production"}
        secret_paths = frozenset({"password"})
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["password"] == "my*****23"
        assert result["host"] == "production"

    def test_mask_nested_secret(self):
        data = {"database": {"password": "secret123", "host": "production"}}
        secret_paths = frozenset({"database.password"})
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["database"]["password"] == "se*****23"
        assert result["database"]["host"] == "production"

    def test_mask_non_string_value(self):
        data = {"token": 123456}
        secret_paths = frozenset({"token"})
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["token"] == "12*****56"

    def test_list_in_data(self):
        data = {"hosts": ["a", "b"], "password": "secret"}
        secret_paths = frozenset({"password"})
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["hosts"] == ["a", "b"]
        assert result["password"] == "se*****et"

    def test_heuristic_masking(self):
        data = {"normal_field": "aB3xK9mZ"}
        secret_paths: frozenset[str] = frozenset()
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["normal_field"] == "aB*****mZ"

    def test_no_masking_without_heuristic(self):
        with patch("dature.masking.masking._heuristic_detector", None):
            data = {"field": "some_normal_value"}
            secret_paths: frozenset[str] = frozenset()
            result = mask_json_value(data, secret_paths=secret_paths)
            assert result["field"] == "some_normal_value"

    def test_empty_secret_paths(self):
        data = {"host": "production", "port": 8080}
        result = mask_json_value(data, secret_paths=frozenset())
        assert result == data

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ("hello", "hello"),
            (42, 42),
            (None, None),
        ],
    )
    def test_non_dict_data(self, data, expected):
        assert mask_json_value(data, secret_paths=frozenset()) == expected


class TestMaskFieldOrigins:
    def test_mask_secret_origin(self):
        origins = (
            FieldOrigin(
                key="password",
                value="secret123",
                source_index=0,
                source_file="config.yaml",
                source_loader_type="yaml",
            ),
            FieldOrigin(
                key="host",
                value="production",
                source_index=0,
                source_file="config.yaml",
                source_loader_type="yaml",
            ),
        )
        secret_paths = frozenset({"password"})
        result = mask_field_origins(origins, secret_paths=secret_paths)
        assert result[0].value == "se*****23"
        assert result[1].value == "production"

    def test_no_secret_origins(self):
        origins = (
            FieldOrigin(
                key="host",
                value="production",
                source_index=0,
                source_file="config.yaml",
                source_loader_type="yaml",
            ),
        )
        result = mask_field_origins(origins, secret_paths=frozenset())
        assert result[0].value == "production"


class TestMaskSourceEntries:
    def test_mask_entries(self):
        entries = (
            SourceEntry(
                index=0,
                file_path="config.yaml",
                loader_type="yaml",
                raw_data={"password": "secret123", "host": "production"},
            ),
        )
        secret_paths = frozenset({"password"})
        result = mask_source_entries(entries, secret_paths=secret_paths)
        assert result[0].raw_data["password"] == "se*****23"
        assert result[0].raw_data["host"] == "production"


class TestMaskEnvLine:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("PASSWORD=mysecret", "PASSWORD=my*****et"),
            ("KEY=ab", "KEY=*****"),
            ("  key: value123", "  key: va*****23"),
            ("key: ab", "key: *****"),
            ("random_line", "ra*****ne"),
        ],
    )
    def test_mask_env_line(self, line, expected):
        assert mask_env_line(line) == expected


class TestGracefulDegradation:
    def test_no_masking_without_detector(self):
        with patch("dature.masking.masking._heuristic_detector", None):
            data = {"field": "aB3xK9mZ_looks_random"}
            result = mask_json_value(data, secret_paths=frozenset())
            assert result["field"] == "aB3xK9mZ_looks_random"


_SECRET_VALUE = "super_secret_password_123"
_MASKED_SECRET = "su*****23"
_PUBLIC_VALUE = "production"


class TestSecretMaskingIntegration:
    def test_load_report_masks_secrets(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"password": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        @dataclass
        class Cfg:
            password: str
            host: str

        result = load(LoadMetadata(file_=json_file), Cfg, debug=True)

        report = get_load_report(result)
        assert report is not None

        assert report.merged_data == {"password": _MASKED_SECRET, "host": _PUBLIC_VALUE}
        assert report.sources[0].raw_data == {"password": _MASKED_SECRET, "host": _PUBLIC_VALUE}

        password_origin = report.field_origins[1]
        assert password_origin.key == "password"
        assert password_origin.value == _MASKED_SECRET

    def test_merge_report_masks_secrets(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(f'{{"password": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text(f'{{"password": "{_SECRET_VALUE}"}}')

        @dataclass
        class Cfg:
            password: str
            host: str

        result = load(
            MergeMetadata(
                sources=(
                    LoadMetadata(file_=defaults),
                    LoadMetadata(file_=overrides),
                ),
            ),
            Cfg,
            debug=True,
        )

        report = get_load_report(result)
        assert report is not None

        assert report.merged_data == {"password": _MASKED_SECRET, "host": _PUBLIC_VALUE}
        assert report.sources[0].raw_data == {"password": _MASKED_SECRET, "host": _PUBLIC_VALUE}
        assert report.sources[1].raw_data == {"password": _MASKED_SECRET}

        password_origin = report.field_origins[1]
        assert password_origin.key == "password"
        assert password_origin.value == _MASKED_SECRET

    def test_load_report_masks_secret_str_type(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"api_key": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        @dataclass
        class Cfg:
            api_key: SecretStr
            host: str

        result = load(LoadMetadata(file_=json_file), Cfg, debug=True)

        report = get_load_report(result)
        assert report is not None

        assert report.merged_data == {"api_key": _MASKED_SECRET, "host": _PUBLIC_VALUE}

        api_key_origin = report.field_origins[0]
        assert api_key_origin.key == "api_key"
        assert api_key_origin.value == _MASKED_SECRET

    def test_debug_logs_mask_secrets(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"password": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        @dataclass
        class Cfg:
            password: str
            host: str

        with caplog.at_level("DEBUG", logger="dature"):
            load(LoadMetadata(file_=json_file), Cfg, debug=True)

        assert _SECRET_VALUE not in caplog.text

    def test_merge_debug_logs_mask_secrets(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(f'{{"password": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text(f'{{"password": "{_SECRET_VALUE}"}}')

        @dataclass
        class Cfg:
            password: str
            host: str

        with caplog.at_level("DEBUG", logger="dature"):
            load(
                MergeMetadata(
                    sources=(
                        LoadMetadata(file_=defaults),
                        LoadMetadata(file_=overrides),
                    ),
                ),
                Cfg,
                debug=True,
            )

        assert _SECRET_VALUE not in caplog.text

    def test_error_message_masks_secrets(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"password": "{_SECRET_VALUE}", "port": "not_a_number"}}')

        @dataclass
        class Cfg:
            password: str
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(LoadMetadata(file_=json_file), Cfg)

        assert _SECRET_VALUE not in str(exc_info.value)

    def test_merge_decorator_error_message_masks_secrets(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"password": "allowed", "host": "prod"}')

        meta = MergeMetadata(
            sources=(LoadMetadata(file_=json_file),),
        )

        @load(meta)
        @dataclass
        class Cfg:
            password: Literal["allowed"]
            host: str

        with pytest.raises(DatureConfigError) as exc_info:
            Cfg(password=_SECRET_VALUE)

        assert _SECRET_VALUE not in str(exc_info.value)

    def test_error_message_heuristic_masks_random_value(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        random_token = "aK9mP2xL5vQ8wR3nJ7yB4zT6"
        content = f'{{"connection_id": "{random_token}", "host": "production"}}'
        json_file.write_text(content)

        @dataclass
        class Cfg:
            connection_id: Literal["conn-1", "conn-2"]
            host: str

        with pytest.raises(DatureConfigError) as exc_info:
            load(LoadMetadata(file_=json_file, mask_secrets=True), Cfg)

        assert str(exc_info.value) == dedent(f"""\
        Cfg loading errors (1)

          [connection_id]  Invalid variant: 'aK*****T6'
           └── FILE '{json_file}', line 1
               {{"connection_id": "aK*****T6", "host": "production"}}
        """)

    def test_error_message_heuristic_no_mask_without_detector(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        random_token = "aK9mP2xL5vQ8wR3nJ7yB4zT6"
        content = f'{{"connection_id": "{random_token}", "host": "production"}}'
        json_file.write_text(content)

        @dataclass
        class Cfg:
            connection_id: Literal["conn-1", "conn-2"]
            host: str

        with patch("dature.masking.masking._heuristic_detector", None), pytest.raises(DatureConfigError) as exc_info:
            load(LoadMetadata(file_=json_file, mask_secrets=True), Cfg)

        assert str(exc_info.value) == dedent(f"""\
        Cfg loading errors (1)

          [connection_id]  Invalid variant: '{random_token}'
           └── FILE '{json_file}', line 1
               {content}
        """)
