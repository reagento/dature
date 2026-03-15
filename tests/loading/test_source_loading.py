"""Tests for loading/source_loading.py — skip broken sources, expand env vars."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

from dature import LoadMetadata, MergeMetadata, load
from dature.errors.exceptions import DatureConfigError, EnvVarExpandError


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
            MergeMetadata(
                sources=(
                    LoadMetadata(file_=valid),
                    LoadMetadata(file_=missing),
                ),
                skip_broken_sources=True,
            ),
            Config,
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
            MergeMetadata(
                sources=(
                    LoadMetadata(file_=valid),
                    LoadMetadata(file_=broken),
                ),
                skip_broken_sources=True,
            ),
            Config,
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
                MergeMetadata(
                    sources=(
                        LoadMetadata(file_=broken_a),
                        LoadMetadata(file_=broken_b),
                    ),
                    skip_broken_sources=True,
                ),
                Config,
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
                MergeMetadata(
                    sources=(
                        LoadMetadata(file_=valid),
                        LoadMetadata(file_=broken),
                    ),
                ),
                Config,
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
            MergeMetadata(
                sources=(
                    LoadMetadata(file_=a),
                    LoadMetadata(file_=broken),
                    LoadMetadata(file_=c),
                ),
                skip_broken_sources=True,
            ),
            Config,
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
            MergeMetadata(
                sources=(
                    LoadMetadata(file_=valid),
                    LoadMetadata(file_=broken, skip_if_broken=True),
                ),
                skip_broken_sources=False,
            ),
            Config,
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
                MergeMetadata(
                    sources=(
                        LoadMetadata(file_=valid),
                        LoadMetadata(file_=broken, skip_if_broken=False),
                    ),
                    skip_broken_sources=True,
                ),
                Config,
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
            MergeMetadata(
                sources=(
                    LoadMetadata(file_=valid),
                    LoadMetadata(file_=broken, skip_if_broken=None),
                ),
                skip_broken_sources=True,
            ),
            Config,
        )

        assert result.host == "localhost"
        assert result.port == 3000

    def test_empty_sources_raises(self):
        @dataclass
        class Config:
            host: str

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                MergeMetadata(sources=()),
                Config,
            )

        assert str(exc_info.value) == "Config loading errors (1)"
        assert str(exc_info.value.exceptions[0]) == "MergeMetadata.sources must not be empty"

    def test_all_sources_broken_mixed_errors(self, tmp_path: Path):
        missing = str(tmp_path / "does_not_exist.json")

        broken = tmp_path / "broken.json"
        broken.write_text("{bad")

        @dataclass
        class Config:
            host: str

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                MergeMetadata(
                    sources=(
                        LoadMetadata(file_=missing),
                        LoadMetadata(file_=broken),
                    ),
                    skip_broken_sources=True,
                ),
                Config,
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
            MergeMetadata(
                sources=(LoadMetadata(file_=json_file),),
            ),
            Config,
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
            MergeMetadata(
                sources=(LoadMetadata(file_=json_file),),
                expand_env_vars="disabled",
            ),
            Config,
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
                MergeMetadata(
                    sources=(LoadMetadata(file_=json_file),),
                    expand_env_vars="strict",
                ),
                Config,
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
            MergeMetadata(
                sources=(LoadMetadata(file_=json_file, expand_env_vars="disabled"),),
                expand_env_vars="default",
            ),
            Config,
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
            MergeMetadata(
                sources=(LoadMetadata(file_=json_file, expand_env_vars=None),),
                expand_env_vars="disabled",
            ),
            Config,
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
            MergeMetadata(
                sources=(LoadMetadata(file_=json_file),),
                expand_env_vars="empty",
            ),
            Config,
        )

        assert result.host == ""


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@dataclass
class StrictConfig:
    host: str
    port: int


class TestEnvVarExpandErrorFormat:
    @pytest.mark.parametrize(
        ("ext", "prefix", "source_label", "line", "line_content"),
        [
            ("yaml", None, "FILE", 1, 'host: "$MISSING_HOST"'),
            ("json", None, "FILE", 1, '{"host": "$MISSING_HOST", "port": 8080}'),
            ("toml", None, "FILE", 1, 'host = "$MISSING_HOST"'),
            ("ini", "section", "FILE", 2, "host = $MISSING_HOST"),
            ("env", None, "ENV FILE", 1, "HOST=$MISSING_HOST"),
        ],
        ids=["yaml", "json", "toml", "ini", "env"],
    )
    def test_error_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        ext: str,
        prefix: str | None,
        source_label: str,
        line: int,
        line_content: str,
    ) -> None:
        monkeypatch.delenv("MISSING_HOST", raising=False)
        file = FIXTURES_DIR / f"env_expand_strict.{ext}"

        with pytest.raises(EnvVarExpandError) as exc_info:
            load(
                LoadMetadata(file_=file, prefix=prefix, expand_env_vars="strict"),
                StrictConfig,
            )

        assert str(exc_info.value) == dedent(f"""\
            StrictConfig env expand errors (1)

              [host]  Missing environment variable 'MISSING_HOST'
               └── {source_label} '{file}', line {line}
                   {line_content}
        """)
