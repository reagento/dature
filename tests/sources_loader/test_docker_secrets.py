from dataclasses import dataclass
from pathlib import Path

from dature import Source, load
from dature.sources_loader.docker_secrets import DockerSecretsLoader
from examples.all_types_dataclass import EXPECTED_ALL_TYPES, AllPythonTypesCompact
from tests.sources_loader.checker import assert_all_types_equal


class TestDockerSecretsLoader:
    def test_comprehensive_type_conversion(self, all_types_docker_secrets_dir: Path):
        result = load(
            Source(file=all_types_docker_secrets_dir, loader=DockerSecretsLoader),
            dataclass_=AllPythonTypesCompact,
        )

        assert_all_types_equal(result, EXPECTED_ALL_TYPES)

    def test_custom_split_symbols(self, tmp_path: Path):
        (tmp_path / "db.host").write_text("localhost")
        (tmp_path / "db.port").write_text("5432")

        loader = DockerSecretsLoader(split_symbols=".")
        result = loader.load_raw(tmp_path)

        assert result.data == {"db": {"host": "localhost", "port": 5432}}

    def test_prefix_filtering(self, tmp_path: Path):
        (tmp_path / "APP_name").write_text("myapp")
        (tmp_path / "APP_port").write_text("8080")
        (tmp_path / "OTHER_key").write_text("ignored")

        loader = DockerSecretsLoader(prefix="APP_")
        data = loader._load(tmp_path)

        assert data == {"name": "myapp", "port": "8080"}

    def test_skip_subdirectories(self, tmp_path: Path):
        (tmp_path / "name").write_text("myapp")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested_file").write_text("should_be_ignored")

        loader = DockerSecretsLoader()
        data = loader._load(tmp_path)

        assert data == {"name": "myapp"}

    def test_empty_directory(self, tmp_path: Path):
        loader = DockerSecretsLoader()
        data = loader._load(tmp_path)

        assert data == {}

    def test_strip_filecontent(self, tmp_path: Path):
        (tmp_path / "secret").write_text("  password123\n")

        loader = DockerSecretsLoader()
        data = loader._load(tmp_path)

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
            Source(file=tmp_path, loader=DockerSecretsLoader),
            dataclass_=Config,
        )

        assert result.api_url == "https://api.example.com/v1"
        assert result.base == "https://api.example.com"
        assert result.base == "https://api.example.com"
