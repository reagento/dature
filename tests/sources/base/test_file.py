import sys
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path

import pytest

import dature
from dature import JsonSource
from dature.config import default_config
from dature.errors import DatureConfigError, FieldLoadError
from dature.sources.base import FileFieldMixin
from dature.sources.yaml_ import Yaml12Source


@pytest.fixture(params=[StringIO("data"), BytesIO(b"data")])
def stream_fixture(request):
    return request.param


class TestFileFieldMixin:
    @pytest.mark.parametrize(
        ("file_input", "expected_file", "expected_type"),
        [
            ("/data/test.json", "/data/test.json", str),
            (Path("/data/test.json"), str(Path("/data/test.json")), str),
            (None, None, type(None)),
        ],
    )
    def test_post_init_file_field(self, file_input, expected_file, expected_type):
        @dataclass
        class Src(FileFieldMixin):
            pass

        src = Src(file=file_input)

        assert src.file == expected_file
        assert isinstance(src.file, expected_type)

    def test_post_init_file_field_stream(self, stream_fixture):
        @dataclass
        class Src(FileFieldMixin):
            pass

        src = Src(file=stream_fixture)

        assert src.file is stream_fixture

    @pytest.mark.parametrize(
        ("file_input", "expected_type"),
        [
            ("config.json", Path),
            (Path("config.json"), Path),
            (None, Path),
        ],
    )
    def test_resolve_file_field_path_types(self, file_input, expected_type):
        result = FileFieldMixin.resolve_file_field(file_input)

        assert isinstance(result, expected_type)

    def test_resolve_file_field_stream(self, stream_fixture):
        result = FileFieldMixin.resolve_file_field(stream_fixture)

        assert result is stream_fixture

    @pytest.mark.parametrize(
        ("file_input", "expected"),
        [
            ("config.json", "config.json"),
            (Path("config.json"), "config.json"),
            ("", ""),
            (None, None),
            (StringIO("data"), "<stream>"),
            (BytesIO(b"data"), "<stream>"),
        ],
    )
    def test_file_field_display(self, file_input, expected):
        result = FileFieldMixin.file_field_display(file_input)

        assert result == expected

    @pytest.mark.parametrize(
        ("file_input", "expected"),
        [
            ("config.json", Path("config.json")),
            (Path("config.json"), Path("config.json")),
            ("", Path()),
            (None, None),
            (StringIO("data"), None),
            (BytesIO(b"data"), None),
        ],
    )
    def test_file_field_path_for_errors(self, file_input, expected):
        result = FileFieldMixin.file_field_path_for_errors(file_input)

        assert result == expected

    @pytest.mark.parametrize(
        ("method_name", "expected_transform"),
        [
            ("file_display", str),
            ("file_path_for_errors", lambda p: p),
        ],
    )
    def test_file_display_and_path_for_errors_with_resolved_path(self, tmp_path: Path, method_name, expected_transform):
        """``Src`` mixes in ``FileFieldMixin`` without ``Source`` — this also exercises the
        ``_redact`` getattr fallback, since a bare mixin has no ``redact`` method to delegate to.
        """

        @dataclass
        class Src(FileFieldMixin):
            pass

        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        src = Src(file=config_file)
        result = getattr(src, method_name)()

        assert result == expected_transform(config_file)


@pytest.mark.usefixtures("_reset_config")
class TestFileSourceSearch:
    """Tests for FileSource system path search (FileFieldMixin._resolved_file_path)."""

    @dataclass
    class _Cfg:
        host: str
        port: int

    def test_finds_file_in_cwd(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("host: localhost\nport: 8080")

        result = dature.load(Yaml12Source(file="config.yaml"), schema=self._Cfg)

        assert result.host == "localhost"
        assert result.port == 8080

    def test_config_dirs_search_disabled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        system_dir = tmp_path / "system_config"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: system\nport: 9000")
        (tmp_path / "config.yaml").write_text("host: cwd\nport: 1000")

        monkeypatch.setenv("DATURE_LOADING__CONFIG_DIRS", "")
        default_config.cache_clear()

        result = dature.load(Yaml12Source(file="config.yaml"), schema=self._Cfg)

        assert result.host == "cwd"
        assert result.port == 1000

    def test_finds_in_custom_dirs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        custom_dir = tmp_path / "custom_config"
        custom_dir.mkdir()
        (custom_dir / "app.yaml").write_text("host: custom\nport: 3000")

        result = dature.load(
            Yaml12Source(file="app.yaml", config_dirs=(custom_dir,)),
            schema=self._Cfg,
        )

        assert result.host == "custom"
        assert result.port == 3000

    def test_priority_cwd_before_system(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.json").write_text('{"host": "cwd", "port": 1111}')
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.json").write_text('{"host": "system", "port": 2222}')

        result = dature.load(
            JsonSource(file="config.json", config_dirs=(system_dir,)),
            schema=self._Cfg,
        )

        assert result.host == "cwd"
        assert result.port == 1111

    def test_disable_search_per_source(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: system\nport: 5000")
        (tmp_path / "config.yaml").write_text("host: cwd\nport: 1000")

        result = dature.load(
            Yaml12Source(
                file="config.yaml",
                config_dirs=(),
            ),
            schema=self._Cfg,
        )

        assert result.host == "cwd"
        assert result.port == 1000

    def test_source_config_dirs_overrides_global_disabled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DATURE_LOADING__CONFIG_DIRS", "")
        default_config.cache_clear()

        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: enabled\nport: 6000")

        result = dature.load(
            Yaml12Source(
                file="config.yaml",
                config_dirs=(system_dir,),
            ),
            schema=self._Cfg,
        )

        assert result.host == "enabled"
        assert result.port == 6000

    def test_uses_default_loading_config_mapping(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

        xdg_dir = tmp_path / "xdg"
        xdg_dir.mkdir()
        (xdg_dir / "config.yaml").write_text("host: default\nport: 7000")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_dir))
        monkeypatch.setattr(sys, "platform", "linux")

        result = dature.load(Yaml12Source(file="config.yaml"), schema=self._Cfg)

        assert result.host == "default"
        assert result.port == 7000

    def test_user_override_via_platform_mapping(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: mapped\nport: 8000")

        # Platform-keyed mappings can't be expressed via a single env var — use an
        # explicit Dature instance instead.
        conf = dature.Dature(loading={"config_dirs": {sys.platform: (system_dir,)}})
        result = conf.load(Yaml12Source(file="config.yaml"), schema=self._Cfg)

        assert result.host == "mapped"
        assert result.port == 8000


@pytest.mark.usefixtures("_reset_config")
class TestConfigDirsDeprecations:
    """system_config_dirs / search_system_paths are deprecated, removed in dature 1.6."""

    @dataclass
    class _Cfg:
        host: str
        port: int

    def test_system_config_dirs_on_source_warns_and_behaves_like_config_dirs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        custom_dir = tmp_path / "custom_config"
        custom_dir.mkdir()
        (custom_dir / "app.yaml").write_text("host: custom\nport: 3000")

        with pytest.warns(DeprecationWarning, match="system_config_dirs"):
            result = dature.load(
                Yaml12Source(file="app.yaml", system_config_dirs=(custom_dir,)),
                schema=self._Cfg,
            )

        assert result.host == "custom"
        assert result.port == 3000

    def test_search_system_paths_false_on_source_warns_and_disables_search(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: system\nport: 5000")
        (tmp_path / "config.yaml").write_text("host: cwd\nport: 1000")

        with pytest.warns(DeprecationWarning, match="search_system_paths"):
            result = dature.load(
                Yaml12Source(
                    file="config.yaml",
                    search_system_paths=False,
                    system_config_dirs=(system_dir,),
                ),
                schema=self._Cfg,
            )

        assert result.host == "cwd"
        assert result.port == 1000

    def test_system_config_dirs_on_dature_loading_warns(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: mapped\nport: 8000")

        with pytest.warns(DeprecationWarning, match="system_config_dirs"):
            conf = dature.Dature(
                loading={"system_config_dirs": {sys.platform: (system_dir,)}},
            )

        result = conf.load(Yaml12Source(file="config.yaml"), schema=self._Cfg)

        assert result.host == "mapped"
        assert result.port == 8000

    def test_search_system_paths_false_on_dature_loading_warns(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        system_dir = tmp_path / "system_config"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: system\nport: 9000")
        (tmp_path / "config.yaml").write_text("host: cwd\nport: 1000")

        with pytest.warns(DeprecationWarning, match="search_system_paths"):
            conf = dature.Dature(
                loading={"search_system_paths": False, "system_config_dirs": (system_dir,)},
            )

        result = conf.load(Yaml12Source(file="config.yaml"), schema=self._Cfg)

        assert result.host == "cwd"
        assert result.port == 1000

    def test_search_system_paths_on_load_warns(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        (system_dir / "config.yaml").write_text("host: system\nport: 5000")
        (tmp_path / "config.yaml").write_text("host: cwd\nport: 1000")

        with pytest.warns(DeprecationWarning, match="search_system_paths"):
            result = dature.load(
                Yaml12Source(file="config.yaml", config_dirs=(system_dir,)),
                schema=self._Cfg,
                search_system_paths=False,
            )

        assert result.host == "cwd"
        assert result.port == 1000


@pytest.mark.usefixtures("_reset_config")
class TestConfigDirsCascade:
    """config_dirs cascades source > load > config, mirroring the strict cascade."""

    @dataclass
    class _Cfg:
        host: str
        port: int

    def test_load_level_config_dirs_fills_unset_source_field(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        custom_dir = tmp_path / "custom_config"
        custom_dir.mkdir()
        (custom_dir / "app.yaml").write_text("host: custom\nport: 3000")

        result = dature.load(
            Yaml12Source(file="app.yaml"),
            schema=self._Cfg,
            config_dirs=(custom_dir,),
        )

        assert result.host == "custom"
        assert result.port == 3000

    def test_source_level_config_dirs_overrides_load_level(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        load_dir = tmp_path / "load_config"
        load_dir.mkdir()
        (load_dir / "app.yaml").write_text("host: load\nport: 4000")
        source_dir = tmp_path / "source_config"
        source_dir.mkdir()
        (source_dir / "app.yaml").write_text("host: source\nport: 5000")

        result = dature.load(
            Yaml12Source(file="app.yaml", config_dirs=(source_dir,)),
            schema=self._Cfg,
            config_dirs=(load_dir,),
        )

        assert result.host == "source"
        assert result.port == 5000


@pytest.mark.usefixtures("_reset_config")
class TestFileSourceEncoding:
    @dataclass
    class _Cfg:
        name: str

    def test_default_encoding_loads_utf8(self, tmp_path: Path) -> None:
        (tmp_path / "config.json").write_bytes('{"name": "hello"}'.encode("utf-8"))  # noqa: UP012
        result = dature.load(JsonSource(file=tmp_path / "config.json"), schema=self._Cfg)
        assert result.name == "hello"

    @pytest.mark.parametrize("encoding", ["cp1251", "cp866"])
    def test_source_level_encoding(self, tmp_path: Path, encoding: str) -> None:
        content = '{"name": "Привет"}'
        (tmp_path / "config.json").write_bytes(content.encode(encoding))
        result = dature.load(
            JsonSource(file=tmp_path / "config.json", encoding=encoding),
            schema=self._Cfg,
        )
        assert result.name == "Привет"

    def test_wrong_encoding_raises(self, tmp_path: Path) -> None:
        (tmp_path / "config.json").write_bytes('{"name": "Привет"}'.encode("cp1251"))
        with pytest.raises((DatureConfigError, UnicodeDecodeError)):
            dature.load(JsonSource(file=tmp_path / "config.json", encoding="utf-8"), schema=self._Cfg)

    def test_global_config_encoding_applied(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "config.json").write_bytes('{"name": "Привет"}'.encode("cp1251"))
        monkeypatch.setenv("DATURE_LOADING__ENCODING", "cp1251")
        default_config.cache_clear()
        result = dature.load(JsonSource(file=tmp_path / "config.json"), schema=self._Cfg)
        assert result.name == "Привет"

    def test_source_level_encoding_wins_over_global(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "config.json").write_bytes('{"name": "Привет"}'.encode("cp1251"))
        monkeypatch.setenv("DATURE_LOADING__ENCODING", "utf-8")
        default_config.cache_clear()
        result = dature.load(
            JsonSource(file=tmp_path / "config.json", encoding="cp1251"),
            schema=self._Cfg,
        )
        assert result.name == "Привет"

    def test_error_location_uses_source_encoding(self, tmp_path: Path) -> None:
        # File has Cyrillic bytes (cp1251); without the fix read_file_content falls
        # back to the platform default encoding, gets UnicodeDecodeError, and
        # returns None — leaving the error location without line_content.
        @dataclass
        class _CfgNotes:
            name: str
            notes: str

        content = '{"name": 42, "notes": "Привет мир"}'
        (tmp_path / "config.json").write_bytes(content.encode("cp1251"))
        with pytest.raises(DatureConfigError) as exc_info:
            dature.load(JsonSource(file=tmp_path / "config.json", encoding="cp1251"), schema=_CfgNotes)
        errors = list(exc_info.value.exceptions)
        assert isinstance(errors[0], FieldLoadError)
        assert errors[0].locations[0].line_content is not None
