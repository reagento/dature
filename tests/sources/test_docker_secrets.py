from dataclasses import dataclass
from pathlib import Path

from dature import DockerSecretsSource, load
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources.checker import assert_all_types_equal


class TestDockerSecretsSource:
    def test_comprehensive_type_conversion(self, all_types_docker_secrets_dir: Path):
        result = load(
            DockerSecretsSource(dir_=all_types_docker_secrets_dir),
            schema=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_custom_split_symbols(self, tmp_path: Path):
        (tmp_path / "db.host").write_text("localhost")
        (tmp_path / "db.port").write_text("5432")

        loader = DockerSecretsSource(dir_=tmp_path, split_symbols=".")
        result = loader.load_raw()

        assert result.data == {"db": {"host": "localhost", "port": 5432}}

    def test_prefix_filtering(self, tmp_path: Path):
        (tmp_path / "APP_name").write_text("myapp")
        (tmp_path / "APP_port").write_text("8080")
        (tmp_path / "OTHER_key").write_text("ignored")

        loader = DockerSecretsSource(dir_=tmp_path, prefix="APP_")
        data = loader._load()

        assert data == {"name": "myapp", "port": "8080"}

    def test_skip_subdirectories(self, tmp_path: Path):
        (tmp_path / "name").write_text("myapp")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested_file").write_text("should_be_ignored")

        loader = DockerSecretsSource(dir_=tmp_path)
        data = loader._load()

        assert data == {"name": "myapp"}

    def test_empty_directory(self, tmp_path: Path):
        loader = DockerSecretsSource(dir_=tmp_path)
        data = loader._load()

        assert data == {}

    def test_strip_file_content(self, tmp_path: Path):
        (tmp_path / "secret").write_text("  password123\n")

        loader = DockerSecretsSource(dir_=tmp_path)
        data = loader._load()

        assert data == {"secret": "password123"}

    def test_env_var_substitution(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("BASE_URL", "https://api.example.com")

        (tmp_path / "api_url").write_text("$BASE_URL/v1")
        (tmp_path / "base").write_text("$BASE_URL")

        @dataclass
        class Config:
            api_url: str
            base: str

        result = load(
            DockerSecretsSource(dir_=tmp_path),
            schema=Config,
        )

        assert result.api_url == "https://api.example.com/v1"
        assert result.base == "https://api.example.com"
        assert result.base == "https://api.example.com"
        assert result.base == "https://api.example.com"
        assert result.base == "https://api.example.com"
        assert result.base == "https://api.example.com"


class TestDockerSecretsDisplayProperties:
    def test_format_name_and_label(self):
        assert DockerSecretsSource.format_name == "docker_secrets"
        assert DockerSecretsSource.location_label == "SECRET FILE"


class TestDockerSecretsResolveLocation:
    def test_resolve_builds_secret_path(self, tmp_path: Path):
        locations = DockerSecretsSource.resolve_location(
            field_path=["db_password"],
            file_path=tmp_path,
            file_content=None,
            prefix=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].file_path == tmp_path / "db_password"
        assert locations[0].line_range is None
        assert locations[0].location_label == "SECRET FILE"

    def test_resolve_with_prefix(self, tmp_path: Path):
        locations = DockerSecretsSource.resolve_location(
            field_path=["password"],
            file_path=tmp_path,
            file_content=None,
            prefix="APP_",
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].file_path == tmp_path / "APP_password"

    def test_resolve_nested_path(self, tmp_path: Path):
        locations = DockerSecretsSource.resolve_location(
            field_path=["database", "host"],
            file_path=tmp_path,
            file_content=None,
            prefix=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].file_path == tmp_path / "database__host"

    def test_resolve_file_path_none(self):
        locations = DockerSecretsSource.resolve_location(
            field_path=["secret"],
            file_path=None,
            file_content=None,
            prefix=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].file_path is None
