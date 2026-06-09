"""Tests for loading/source_loading.py — skip broken sources, expand env vars."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

from dature import EnvFileSource, IniSource, JsonSource, Toml11Source, Yaml12Source, load
from dature.errors import DatureConfigError, EnvVarExpandError
from dature.loading.context import build_error_ctx
from dature.loading.source_loading import prepare_loaded_source
from dature.types import LoadRawResult


class TestSkipBrokenSources:
    def test_skip_missing_file(self, tmp_path: Path):
        valid = tmp_path / "valid.json"
        valid.write_text('{"host": "localhost", "port": 3000}')

        missing = str(tmp_path / "does_not_exist.json")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=valid),
            JsonSource(file=missing),
            schema=Config,
            skip_broken_sources=True,
        )

        assert result.host == "localhost"
        assert result.port == 3000

    def test_skip_broken_json(self, tmp_path: Path):
        valid = tmp_path / "valid.json"
        valid.write_text('{"host": "localhost", "port": 3000}')

        broken = tmp_path / "broken.json"
        broken.write_text("{invalid json")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=valid),
            JsonSource(file=broken),
            schema=Config,
            skip_broken_sources=True,
        )

        assert result.host == "localhost"
        assert result.port == 3000

    def test_all_sources_broken_raises(self, tmp_path: Path):
        broken_a = tmp_path / "a.json"
        broken_a.write_text("{bad")

        broken_b = tmp_path / "b.json"
        broken_b.write_text("{bad")

        @dataclass
        class Config:
            host: str

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(file=broken_a),
                JsonSource(file=broken_b),
                schema=Config,
                skip_broken_sources=True,
            )

        assert str(exc_info.value) == "Config loading errors (1)"
        assert str(exc_info.value.exceptions[0]) == "All 2 source(s) failed to load"

    def test_broken_source_without_flag_raises(self, tmp_path: Path):
        valid = tmp_path / "valid.json"
        valid.write_text('{"host": "localhost"}')

        broken = tmp_path / "broken.json"
        broken.write_text("{bad")

        @dataclass
        class Config:
            host: str

        with pytest.raises(DatureConfigError):
            load(
                JsonSource(file=valid),
                JsonSource(file=broken),
                schema=Config,
            )

    def test_skip_middle_source(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "a-host", "port": 1000}')

        broken = tmp_path / "broken.json"
        broken.write_text("{bad")

        c = tmp_path / "c.json"
        c.write_text('{"port": 2000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=a),
            JsonSource(file=broken),
            JsonSource(file=c),
            schema=Config,
            skip_broken_sources=True,
        )

        assert result.host == "a-host"
        assert result.port == 2000

    def test_per_source_override_skip(self, tmp_path: Path):
        valid = tmp_path / "valid.json"
        valid.write_text('{"host": "localhost", "port": 3000}')

        broken = tmp_path / "broken.json"
        broken.write_text("{bad")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=valid),
            JsonSource(file=broken, skip_if_broken=True),
            schema=Config,
            skip_broken_sources=False,
        )

        assert result.host == "localhost"
        assert result.port == 3000

    def test_per_source_override_no_skip(self, tmp_path: Path):
        valid = tmp_path / "valid.json"
        valid.write_text('{"host": "localhost", "port": 3000}')

        broken = tmp_path / "broken.json"
        broken.write_text("{bad")

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(DatureConfigError):
            load(
                JsonSource(file=valid),
                JsonSource(file=broken, skip_if_broken=False),
                schema=Config,
                skip_broken_sources=True,
            )

    def test_per_source_none_uses_global(self, tmp_path: Path):
        valid = tmp_path / "valid.json"
        valid.write_text('{"host": "localhost", "port": 3000}')

        broken = tmp_path / "broken.json"
        broken.write_text("{bad")

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=valid),
            JsonSource(file=broken, skip_if_broken=None),
            schema=Config,
            skip_broken_sources=True,
        )

        assert result.host == "localhost"
        assert result.port == 3000

    def test_empty_sources_raises(self):
        with pytest.raises(TypeError, match="load\\(\\) requires at least one Source"):
            load(schema=int)

    def test_all_sources_broken_mixed_errors(self, tmp_path: Path):
        missing = str(tmp_path / "does_not_exist.json")

        broken = tmp_path / "broken.json"
        broken.write_text("{bad")

        @dataclass
        class Config:
            host: str

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(file=missing),
                JsonSource(file=broken),
                schema=Config,
                skip_broken_sources=True,
            )

        assert str(exc_info.value) == "Config loading errors (1)"
        assert str(exc_info.value.exceptions[0]) == "All 2 source(s) failed to load"


class TestMergeExpandEnvVars:
    def test_merge_level_default_expands(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DATURE_HOST", "from-env")
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "$DATURE_HOST", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=json_file),
            schema=Config,
        )

        assert result.host == "from-env"

    def test_merge_level_disabled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DATURE_HOST", "from-env")
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "$DATURE_HOST", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=json_file),
            schema=Config,
            expand_env_vars="disabled",
        )

        assert result.host == "$DATURE_HOST"

    def test_merge_level_strict_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "$DATURE_MISSING", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(EnvVarExpandError):
            load(
                JsonSource(file=json_file),
                schema=Config,
                expand_env_vars="strict",
            )

    def test_source_overrides_merge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DATURE_HOST", "from-env")
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "$DATURE_HOST", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=json_file, expand_env_vars="disabled"),
            schema=Config,
            expand_env_vars="default",
        )

        assert result.host == "$DATURE_HOST"

    def test_source_none_inherits_merge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DATURE_HOST", "from-env")
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "$DATURE_HOST", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=json_file, expand_env_vars=None),
            schema=Config,
            expand_env_vars="disabled",
        )

        assert result.host == "$DATURE_HOST"

    def test_merge_level_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "$DATURE_MISSING", "port": 8080}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            JsonSource(file=json_file),
            schema=Config,
            expand_env_vars="empty",
        )

        assert result.host == ""


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@dataclass
class StrictConfig:
    host: str
    port: int


class TestEnvVarExpandErrorFormat:
    @pytest.mark.parametrize(
        ("source_cls", "source_kwargs", "source_label", "line", "line_content"),
        [
            (Yaml12Source, {"file": FIXTURES_DIR / "env_expand_strict.yaml"}, "FILE", 1, 'host: "$MISSING_HOST"'),
            (
                JsonSource,
                {"file": FIXTURES_DIR / "env_expand_strict.json"},
                "FILE",
                1,
                '{"host": "$MISSING_HOST", "port": 8080}',
            ),
            (Toml11Source, {"file": FIXTURES_DIR / "env_expand_strict.toml"}, "FILE", 1, 'host = "$MISSING_HOST"'),
            (
                IniSource,
                {"file": FIXTURES_DIR / "env_expand_strict.ini", "prefix": "section"},
                "FILE",
                2,
                "host = $MISSING_HOST",
            ),
            (EnvFileSource, {"file": FIXTURES_DIR / "env_expand_strict.env"}, "ENV FILE", 1, "HOST=$MISSING_HOST"),
        ],
        ids=["yaml", "json", "toml", "ini", "env"],
    )
    def test_error_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        source_cls: type,
        source_kwargs: dict[str, object],
        source_label: str,
        line: int,
        line_content: str,
    ) -> None:
        monkeypatch.delenv("MISSING_HOST", raising=False)
        file = source_kwargs["file"]

        with pytest.raises(EnvVarExpandError) as exc_info:
            load(
                source_cls(**source_kwargs, expand_env_vars="strict"),
                schema=StrictConfig,
            )

        eq_pos = line_content.find("=")
        caret_pos = eq_pos + 1 if eq_pos != -1 else 0
        caret_len = len(line_content) - caret_pos
        assert str(exc_info.value) == dedent(f"""\
            StrictConfig env expand errors (1)

              [host]  Missing environment variable 'MISSING_HOST'
               ├── {line_content}
               │   {" " * caret_pos}{"^" * caret_len}
               └── {source_label} '{file}', line {line}
        """)


class TestPrepareLoadedSource:
    """Unit tests for the shared per-source pre-processing tail."""

    @pytest.mark.parametrize(
        ("skip_value", "raw_data"),
        [
            pytest.param(None, {"name": "hello"}, id="skip_none_passes_through"),
            pytest.param(False, {"name": "hello"}, id="skip_false_passes_through"),
        ],
    )
    def test_no_filtering_returns_raw(self, tmp_path: Path, skip_value, raw_data):
        json_file = tmp_path / "c.json"
        json_file.write_text("{}")

        @dataclass
        class Cfg:
            name: str

        source = JsonSource(file=json_file)
        error_ctx = build_error_ctx(source, "Cfg")
        load_result = LoadRawResult(data=raw_data)

        result = prepare_loaded_source(
            load_result=load_result,
            source=source,
            schema=Cfg,
            dataclass_name="Cfg",
            base_error_ctx=error_ctx,
            skip_value=skip_value,
            secret_paths=frozenset(),
            mask_secrets=False,
            log_prefix="[Cfg]",
            probe_retort=None,
        )

        assert result.raw_data == raw_data
        assert result.skipped == []
