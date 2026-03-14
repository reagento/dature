from dataclasses import dataclass, field
from pathlib import Path

import pytest

from dature import LoadMetadata, load


class TestPostInitValidationFunctionMode:
    def test_post_init_success(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int
            host: str

            def __post_init__(self) -> None:
                if self.port < 0 or self.port > 65535:
                    msg = f"Invalid port: {self.port}"
                    raise ValueError(msg)

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080, "host": "localhost"}')

        result = load(LoadMetadata(file_=json_file), Config)

        assert result.port == 8080
        assert result.host == "localhost"

    def test_post_init_failure(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int
            host: str

            def __post_init__(self) -> None:
                if self.port < 0 or self.port > 65535:
                    msg = f"Invalid port: {self.port}"
                    raise ValueError(msg)

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 99999, "host": "localhost"}')

        with pytest.raises(ValueError, match="Invalid port: 99999"):
            load(LoadMetadata(file_=json_file), Config)

    def test_post_init_cross_field_validation(self, tmp_path: Path):
        @dataclass
        class Config:
            min_value: int
            max_value: int

            def __post_init__(self) -> None:
                if self.min_value >= self.max_value:
                    msg = f"min_value ({self.min_value}) must be less than max_value ({self.max_value})"
                    raise ValueError(msg)

        json_file = tmp_path / "config.json"
        json_file.write_text('{"min_value": 100, "max_value": 10}')

        with pytest.raises(ValueError, match=r"min_value \(100\) must be less than max_value \(10\)"):
            load(LoadMetadata(file_=json_file), Config)

    def test_post_init_cross_field_success(self, tmp_path: Path):
        @dataclass
        class Config:
            min_value: int
            max_value: int

            def __post_init__(self) -> None:
                if self.min_value >= self.max_value:
                    msg = f"min_value ({self.min_value}) must be less than max_value ({self.max_value})"
                    raise ValueError(msg)

        json_file = tmp_path / "config.json"
        json_file.write_text('{"min_value": 1, "max_value": 100}')

        result = load(LoadMetadata(file_=json_file), Config)

        assert result.min_value == 1
        assert result.max_value == 100


class TestPostInitValidationDecoratorMode:
    def test_post_init_success(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080, "host": "localhost"}')

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            port: int
            host: str

            def __post_init__(self) -> None:
                if self.port < 0 or self.port > 65535:
                    msg = f"Invalid port: {self.port}"
                    raise ValueError(msg)

        config = Config()

        assert config.port == 8080
        assert config.host == "localhost"

    def test_post_init_failure_from_file(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 99999, "host": "localhost"}')

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            port: int
            host: str

            def __post_init__(self) -> None:
                if self.port < 0 or self.port > 65535:
                    msg = f"Invalid port: {self.port}"
                    raise ValueError(msg)

        with pytest.raises(ValueError, match="Invalid port: 99999"):
            Config()

    def test_post_init_failure_from_override(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080, "host": "localhost"}')

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            port: int
            host: str

            def __post_init__(self) -> None:
                if self.port < 0 or self.port > 65535:
                    msg = f"Invalid port: {self.port}"
                    raise ValueError(msg)

        with pytest.raises(ValueError, match="Invalid port: -1"):
            Config(port=-1)

    def test_post_init_cross_field(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"min_value": 50, "max_value": 10}')

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            min_value: int
            max_value: int

            def __post_init__(self) -> None:
                if self.min_value >= self.max_value:
                    msg = "min must be less than max"
                    raise ValueError(msg)

        with pytest.raises(ValueError, match="min must be less than max"):
            Config()


class TestPostInitComputedFields:
    def test_computed_field_via_post_init(self, tmp_path: Path):
        @dataclass
        class Config:
            host: str
            port: int
            base_url: str = field(init=False)

            def __post_init__(self) -> None:
                self.base_url = f"http://{self.host}:{self.port}"

        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": 8080}')

        result = load(LoadMetadata(file_=json_file), Config)

        assert result.base_url == "http://localhost:8080"

    def test_computed_field_via_post_init_decorator(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "example.com", "port": 443}')

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            host: str
            port: int
            base_url: str = ""

            def __post_init__(self) -> None:
                self.base_url = f"https://{self.host}:{self.port}"

        config = Config()

        assert config.base_url == "https://example.com:443"


class TestPropertyValidation:
    def test_property_computed_value(self, tmp_path: Path):
        @dataclass
        class Config:
            host: str
            port: int

            @property
            def address(self) -> str:
                return f"{self.host}:{self.port}"

        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": 8080}')

        result = load(LoadMetadata(file_=json_file), Config)

        assert result.address == "localhost:8080"

    def test_property_computed_value_decorator(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"host": "localhost", "port": 3000}')

        @load(LoadMetadata(file_=json_file))
        @dataclass
        class Config:
            host: str
            port: int

            @property
            def address(self) -> str:
                return f"{self.host}:{self.port}"

        config = Config()

        assert config.address == "localhost:3000"

    def test_property_with_validation_logic(self, tmp_path: Path):
        @dataclass
        class Config:
            _email: str

            @property
            def email(self) -> str:
                return self._email.lower().strip()

        json_file = tmp_path / "config.json"
        json_file.write_text('{"_email": "  Admin@Example.COM  "}')

        result = load(LoadMetadata(file_=json_file), Config)

        assert result.email == "admin@example.com"
