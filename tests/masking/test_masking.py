from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import pytest

from dature import JsonSource, Yaml11Source, configure, load, load_report
from dature.errors import DatureConfigError, FieldLoadError
from dature.field_path import F
from dature.fields.secret_str import SecretStr
from dature.masking.masking import (
    is_secret_path,
    mask_env_line,
    mask_field_origins,
    mask_json_value,
    mask_source_entries,
    mask_value,
)
from dature.report_types import FieldOrigin, SourceEntry
from dature.type_aliases import MaskingMode, NameStyle


class TestMaskValue:
    @pytest.mark.parametrize(
        ("input_value", "expected"),
        [
            ("", ""),
            ("a", "<REDACTED>"),
            ("ab", "<REDACTED>"),
            ("abc", "<REDACTED>"),
            ("abcd", "<REDACTED>"),
            ("abcde", "<REDACTED>"),
            ("abcdef", "<REDACTED>"),
            ("abcdefghij", "<REDACTED>"),
            ("my_secret_password_123", "<REDACTED>"),
        ],
    )
    def test_mask_value(self, input_value, expected):
        assert mask_value(input_value) == expected


class TestMaskValueCustomConfig:
    @pytest.mark.usefixtures("_reset_config")
    @pytest.mark.parametrize(
        ("mask", "visible_prefix", "visible_suffix", "input_value", "expected"),
        [
            ("[HIDDEN]", 0, 0, "secret", "[HIDDEN]"),
            ("***", 2, 2, "abcdef", "ab***ef"),
            ("***", 2, 2, "abcd", "abcd"),
            ("***", 2, 2, "abc", "abc"),
            ("***", 3, 0, "abcdef", "abc***"),
            ("***", 0, 3, "abcdef", "***def"),
            ("***", 5, 0, "ab", "ab"),
            ("***", 0, 5, "ab", "ab"),
            ("***", 3, 3, "abcdef", "abcdef"),
            ("<REDACTED>", 2, 2, "abcdefghij", "ab<REDACTED>ij"),
        ],
    )
    def test_mask_value_with_custom_config(
        self,
        mask: str,
        visible_prefix: int,
        visible_suffix: int,
        input_value: str,
        expected: str,
    ):
        configure(
            masking={
                "mask": mask,
                "visible_prefix": visible_prefix,
                "visible_suffix": visible_suffix,
            },
        )
        assert mask_value(input_value) == expected


class TestIsSecretPath:
    @pytest.mark.parametrize(
        ("field_path", "secret_paths", "masking_mode", "expected"),
        [
            ("db.secret-key", frozenset({"db.secret_key"}), "secrets_only", True),
            ("db.secretKey", frozenset({"db.secret_key"}), "secrets_only", True),
            ("db.SecretKey", frozenset({"db.secret_key"}), "secrets_only", True),
            ("db.SECRET_KEY", frozenset({"db.secret_key"}), "secrets_only", True),
            ("db.SECRET-KEY", frozenset({"db.secret_key"}), "secrets_only", True),
            ("host", frozenset({"db.secret_key"}), "secrets_only", False),
            ("api-token", frozenset(), "secrets_only", True),
            ("api-token", frozenset(), "none", False),
            ("host", frozenset(), "all", True),
        ],
        ids=[
            "kebab-leaf",
            "lower-camel-leaf",
            "upper-camel-leaf",
            "upper-snake-leaf",
            "upper-kebab-leaf",
            "no-match",
            "pattern-match-secrets-only",
            "pattern-no-match-mode-none",
            "all-mode-shortcircuits",
        ],
    )
    def test_matching(
        self,
        field_path: str,
        secret_paths: frozenset[str],
        masking_mode: MaskingMode,
        expected: bool,
    ) -> None:
        assert is_secret_path(field_path, secret_paths=secret_paths, masking_mode=masking_mode) is expected


class TestMaskJsonValue:
    def test_mask_secret_string(self):
        data = {"password": "my_secret_123", "host": "production"}
        secret_paths = frozenset({"password"})
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["password"] == "<REDACTED>"
        assert result["host"] == "production"

    def test_mask_nested_secret(self):
        data = {"database": {"password": "secret123", "host": "production"}}
        secret_paths = frozenset({"database.password"})
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["database"]["password"] == "<REDACTED>"
        assert result["database"]["host"] == "production"

    def test_mask_non_string_value(self):
        data = {"token": 123456}
        secret_paths = frozenset({"token"})
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["token"] == "<REDACTED>"

    def test_list_in_data(self):
        data = {"hosts": ["a", "b"], "password": "secret"}
        secret_paths = frozenset({"password"})
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["hosts"] == ["a", "b"]
        assert result["password"] == "<REDACTED>"

    def test_heuristic_masking(self):
        data = {"normal_field": "aB3xK9mZ"}
        secret_paths: frozenset[str] = frozenset()
        result = mask_json_value(data, secret_paths=secret_paths)
        assert result["normal_field"] == "<REDACTED>"

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

    def test_secret_path_dict_value_masks_all_nested_leaves(self):
        data = {"credential": {"a": {"b": "deepleak"}}}
        secret_paths = frozenset({"credential"})

        result = mask_json_value(data, secret_paths=secret_paths, masking_mode="secrets_only")

        assert result == {"credential": {"a": {"b": "<REDACTED>"}}}

    def test_secret_path_list_of_dicts_masks_all_nested_leaves(self):
        data = {"credential": [{"user": "admin", "value": "topsecretvalue"}]}
        secret_paths = frozenset({"credential"})

        result = mask_json_value(data, secret_paths=secret_paths, masking_mode="secrets_only")

        assert result == {"credential": [{"user": "<REDACTED>", "value": "<REDACTED>"}]}

    def test_secret_path_list_of_numbers_masks_every_element(self):
        data = {"credential": [1, 2]}
        secret_paths = frozenset({"credential"})

        result = mask_json_value(data, secret_paths=secret_paths, masking_mode="secrets_only")

        assert result == {"credential": ["<REDACTED>", "<REDACTED>"]}

    def test_masking_mode_all_masks_numbers(self):
        data = {"port": 8080}

        result = mask_json_value(data, secret_paths=frozenset(), masking_mode="all")

        assert result == {"port": "<REDACTED>"}

    def test_secret_path_nested_leak_end_to_end(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"auth": {"user": "admin", "value": "topsecretvalue"}}')

        @dataclass
        class Auth:
            user: str
            value: str

        @dataclass
        class Cfg:
            auth: Auth

        with caplog.at_level("DEBUG", logger="dature"):
            load(JsonSource(file=json_file), schema=Cfg, debug=True)

        messages = [r.message for r in caplog.records if r.message.startswith("[Cfg] Loaded data:")]
        assert messages == ["[Cfg] Loaded data: {'auth': {'user': '<REDACTED>', 'value': '<REDACTED>'}}"]


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
        assert result[0].value == "<REDACTED>"
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
        assert result[0].raw_data["password"] == "<REDACTED>"
        assert result[0].raw_data["host"] == "production"


class TestMaskEnvLine:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("PASSWORD=mysecret", "PASSWORD=<REDACTED>"),
            ("KEY=ab", "KEY=<REDACTED>"),
            ("  key: value123", "  key: <REDACTED>"),
            ("key: ab", "key: <REDACTED>"),
            ("random_line", "<REDACTED>"),
            # Structural lines: keys preserved, values masked
            (
                '{"host": "localhost", "port": 8080}',
                '{"host": "<REDACTED>", "port": <REDACTED>}',
            ),
            (
                'VAR={"foo": "bar", "baz": 42}',
                'VAR={"foo": "<REDACTED>", "baz": <REDACTED>}',
            ),
            (
                'key = {"nested": {"a": 1, "b": "x"}}',
                'key = {"nested": {"a": <REDACTED>, "b": "<REDACTED>"}}',
            ),
            # Bare/unquoted keys (JSON5/YAML-in-braces style)
            (
                "VAR={count: true}",
                "VAR={count: <REDACTED>}",
            ),
            (
                "{foo: 1, bar: 2}",
                "{foo: <REDACTED>, bar: <REDACTED>}",
            ),
            # Array elements are masked too (regression: used to pass through untouched)
            (
                'tags: ["web", "web"],',
                'tags: ["<REDACTED>", "<REDACTED>"],',
            ),
            (
                '[{"user": "admin"}]',
                '[{"user": "<REDACTED>"}]',
            ),
            # Bare key position guards: a colon inside an unquoted value is not a new key
            (
                "url: http://h/p",
                "url: <REDACTED>",
            ),
            # Unclosed / escaped quotes degrade gracefully instead of raising
            (
                '{"host": "unterminated',
                '{"host": "unterminated',
            ),
            (
                '{"host": "esc\\"aped"}',
                '{"host": "<REDACTED>"}',
            ),
        ],
    )
    def test_mask_env_line(self, line, expected):
        assert mask_env_line(line) == expected

    def test_mask_env_line_secrets_only_masks_named_leaf(self):
        line = '{"password": "secret123", "host": "production"}'

        result = mask_env_line(line, masking_mode="secrets_only", secret_leaf_names=frozenset({"password"}))

        assert result == '{"password": "<REDACTED>", "host": "production"}'

    def test_mask_env_line_secret_container_masks_nested_leaves(self):
        line = '{"credential": {"user": "admin", "value": "leak"}}'

        result = mask_env_line(line, masking_mode="secrets_only", secret_leaf_names=frozenset({"credential"}))

        assert result == '{"credential": {"user": "<REDACTED>", "value": "<REDACTED>"}}'

    @pytest.mark.parametrize(
        "raw_key",
        ["secret-key", "secretKey", "SecretKey", "SECRET_KEY"],
        ids=["kebab", "lower-camel", "upper-camel", "upper-snake"],
    )
    def test_secrets_only_masks_styled_leaf(self, raw_key: str) -> None:
        line = f'{{"{raw_key}": "s", "host": "production"}}'

        result = mask_env_line(line, masking_mode="secrets_only", secret_leaf_names=frozenset({"secretkey"}))

        assert result == f'{{"{raw_key}": "<REDACTED>", "host": "production"}}'


class TestGracefulDegradation:
    def test_no_masking_without_detector(self):
        with patch("dature.masking.masking._heuristic_detector", None):
            data = {"field": "aB3xK9mZ_looks_random"}
            result = mask_json_value(data, secret_paths=frozenset())
            assert result["field"] == "aB3xK9mZ_looks_random"


_SECRET_VALUE = "super_secret_password_123"
_MASKED_SECRET = "<REDACTED>"
_PUBLIC_VALUE = "production"


@pytest.mark.usefixtures("_reset_config")
class TestSecretMaskingIntegration:
    def test_load_report_masks_secrets(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"password": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        @dataclass
        class Cfg:
            password: str
            host: str

        configure(masking={"masking_mode": "secrets_only"})
        result = load(JsonSource(file=json_file), schema=Cfg, debug=True)

        report = load_report(result)
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

        configure(masking={"masking_mode": "secrets_only"})
        result = load(
            JsonSource(file=defaults),
            JsonSource(file=overrides),
            schema=Cfg,
            debug=True,
        )

        report = load_report(result)
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

        configure(masking={"masking_mode": "secrets_only"})
        result = load(JsonSource(file=json_file), schema=Cfg, debug=True)

        report = load_report(result)
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
            load(JsonSource(file=json_file), schema=Cfg, debug=True)

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
                JsonSource(file=defaults),
                JsonSource(file=overrides),
                schema=Cfg,
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
            load(JsonSource(file=json_file), schema=Cfg)

        assert _SECRET_VALUE not in str(exc_info.value)

    @pytest.mark.parametrize(
        ("masking_mode", "expected_message"),
        [
            ("none", "invalid literal for int() with base 10: 'not_a_number'"),
            ("secrets_only", "invalid literal for int() with base 10: 'not_a_number'"),
            ("all", "invalid literal for int() with base 10: '<REDACTED>'"),
        ],
    )
    def test_type_coercion_error_message_respects_masking_mode(
        self,
        tmp_path: Path,
        masking_mode: Literal["none", "secrets_only", "all"],
        expected_message: str,
    ) -> None:
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": "not_a_number"}')

        @dataclass
        class Cfg:
            port: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(JsonSource(file=json_file), masking_mode=masking_mode, schema=Cfg)

        field_error = exc_info.value.exceptions[0]
        assert isinstance(field_error, FieldLoadError)
        assert field_error.message == expected_message

    def test_merge_decorator_error_message_masks_secrets(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"password": "allowed", "host": "prod"}')

        @load(JsonSource(file=json_file))
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
            load(JsonSource(file=json_file), masking_mode="secrets_only", schema=Cfg)

        assert str(exc_info.value) == "Cfg loading errors (1)"
        assert str(exc_info.value.exceptions[0]) == (
            "  [connection_id]  Invalid variant: '<REDACTED>'\n"
            f'   ├── {{"connection_id": "<REDACTED>", "host": "production"}}\n'
            f"   │                      ^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

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
            load(JsonSource(file=json_file), masking_mode="secrets_only", schema=Cfg)

        assert str(exc_info.value) == "Cfg loading errors (1)"
        assert str(exc_info.value.exceptions[0]) == (
            f"  [connection_id]  Invalid variant: '{random_token}'\n"
            f"   ├── {content}\n"
            f"   │                      ^^^^^^^^^^^^^^^^^^^^^^^^\n"
            f"   └── FILE '{json_file}', line 1"
        )

    @pytest.mark.usefixtures("_reset_config")
    @pytest.mark.parametrize(
        ("mask_secrets", "expected_password"),
        [
            (True, _MASKED_SECRET),
            (False, _SECRET_VALUE),
        ],
    )
    def test_function_mode_report_respects_global_mask_secrets(
        self,
        tmp_path: Path,
        mask_secrets: bool,
        expected_password: str,
    ):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"password": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        @dataclass
        class Cfg:
            password: str
            host: str

        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            configure(masking={"mask_secrets": mask_secrets})
        result = load(JsonSource(file=json_file), schema=Cfg, debug=True)

        report = load_report(result)
        assert report is not None

        assert report.merged_data == {"password": expected_password, "host": _PUBLIC_VALUE}
        assert report.sources[0].raw_data == {"password": expected_password, "host": _PUBLIC_VALUE}

    @pytest.mark.usefixtures("_reset_config")
    @pytest.mark.parametrize(
        ("mask_secrets", "expected_password"),
        [
            (True, _MASKED_SECRET),
            (False, _SECRET_VALUE),
        ],
    )
    def test_function_mode_error_respects_global_mask_secrets(
        self,
        tmp_path: Path,
        mask_secrets: bool,
        expected_password: str,
    ):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"password": "{_SECRET_VALUE}", "port": "not_a_number"}}')

        @dataclass
        class Cfg:
            password: str
            port: int

        with pytest.warns(DeprecationWarning, match="mask_secrets"):
            configure(masking={"mask_secrets": mask_secrets})

        with pytest.raises(DatureConfigError) as exc_info:
            load(JsonSource(file=json_file), schema=Cfg)

        assert str(exc_info.value) == "Cfg loading errors (1)"
        content = f'{{"password": "{expected_password}", "port": "not_a_number"}}'
        caret_pos = content.rfind("not_a_number")
        assert str(exc_info.value.exceptions[0]) == (
            "  [port]  invalid literal for int() with base 10: 'not_a_number'\n"
            f"   ├── {content}\n"
            f"   │   {' ' * caret_pos}{'^^^^^^^^^^^^'}\n"
            f"   └── FILE '{json_file}', line 1"
        )


def _styled_name(snake_name: str, name_style: NameStyle) -> str:
    parts = snake_name.split("_")
    if name_style == "lower_snake":
        return snake_name
    if name_style == "upper_snake":
        return snake_name.upper()
    if name_style == "lower_camel":
        return parts[0] + "".join(p.capitalize() for p in parts[1:])
    if name_style == "upper_camel":
        return "".join(p.capitalize() for p in parts)
    if name_style == "lower_kebab":
        return snake_name.replace("_", "-")
    return snake_name.replace("_", "-").upper()


_ALL_NAME_STYLES: list[NameStyle] = [
    "lower_snake",
    "upper_snake",
    "lower_camel",
    "upper_camel",
    "lower_kebab",
    "upper_kebab",
]


@pytest.mark.usefixtures("_reset_config")
class TestNameStyleMaskingIntegration:
    @pytest.mark.parametrize("name_style", _ALL_NAME_STYLES)
    @pytest.mark.parametrize("masking_mode", ["all", "secrets_only"])
    def test_report_masks_and_preserves_key(
        self,
        tmp_path: Path,
        name_style: NameStyle,
        masking_mode: MaskingMode,
    ) -> None:
        db_key = _styled_name("db", name_style)
        host_key = _styled_name("host", name_style)
        password_key = _styled_name("password", name_style)
        secret_key = _styled_name("secret_key", name_style)

        @dataclass
        class Db:
            host: str
            password: str
            secret_key: str

        @dataclass
        class Cfg:
            db: Db

        yaml_file = tmp_path / "config.yml"
        yaml_file.write_text(
            f"{db_key}:\n"
            f"  {host_key}: localhost\n"
            f"  {password_key}: single-word-field-name\n"
            f"  {secret_key}: compound-field-name\n",
        )

        source = Yaml11Source(file=yaml_file, name_style=name_style, search_system_paths=False)
        result = load(source, schema=Cfg, masking_mode=masking_mode, debug=True)

        report = load_report(result)
        assert report is not None

        assert report.merged_data == {
            db_key: {
                host_key: _MASKED_SECRET if masking_mode == "all" else "localhost",
                password_key: _MASKED_SECRET,
                secret_key: _MASKED_SECRET,
            },
        }
        assert report.sources[0].raw_data == report.merged_data

    def test_aliased_secret_str_field_masks(self, tmp_path: Path) -> None:
        @dataclass
        class Cfg:
            db_host: SecretStr
            other: str

        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"DATABASE_HOSTNAME": "{_SECRET_VALUE}", "other": "{_PUBLIC_VALUE}"}}')

        source = JsonSource(file=json_file, field_mapping={F[Cfg].db_host: "DATABASE_HOSTNAME"})
        result = load(source, schema=Cfg, masking_mode="secrets_only", debug=True)

        report = load_report(result)
        assert report is not None
        assert report.merged_data == {"DATABASE_HOSTNAME": _MASKED_SECRET, "other": _PUBLIC_VALUE}

    @pytest.mark.parametrize(
        ("masking_mode", "expected"),
        [
            ("secrets_only", {"api-token": _MASKED_SECRET, "host": _PUBLIC_VALUE}),
            ("none", {"api-token": _SECRET_VALUE, "host": _PUBLIC_VALUE}),
        ],
        ids=["secrets-only-masks-pattern-match", "none-masks-nothing"],
    )
    def test_raw_key_pattern_masks_non_schema_key(
        self,
        tmp_path: Path,
        masking_mode: MaskingMode,
        expected: dict[str, str],
    ) -> None:
        @dataclass
        class Cfg:
            extras: dict[str, str]

        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"extras": {{"api-token": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}}}')

        result = load(JsonSource(file=json_file), schema=Cfg, masking_mode=masking_mode, debug=True)

        report = load_report(result)
        assert report is not None
        assert report.merged_data == {"extras": expected}


@pytest.mark.usefixtures("_reset_config")
class TestLoadLevelMaskingParams:
    def test_load_level_masking_mode(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"password": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        @dataclass
        class Cfg:
            password: str
            host: str

        configure(masking={"masking_mode": "none"})
        result = load(JsonSource(file=json_file), schema=Cfg, debug=True, masking_mode="secrets_only")

        report = load_report(result)
        assert report is not None
        assert report.merged_data == {"password": _MASKED_SECRET, "host": _PUBLIC_VALUE}

    def test_load_level_secret_field_names(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text(f'{{"my_token": "{_SECRET_VALUE}", "host": "{_PUBLIC_VALUE}"}}')

        @dataclass
        class Cfg:
            my_token: str
            host: str

        result = load(
            JsonSource(file=json_file),
            schema=Cfg,
            debug=True,
            masking_mode="secrets_only",
            secret_field_names=("my_token",),
        )

        report = load_report(result)
        assert report is not None
        assert report.merged_data == {"my_token": _MASKED_SECRET, "host": _PUBLIC_VALUE}
