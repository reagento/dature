from dataclasses import dataclass
from pathlib import Path

import pytest

from dature import Source, load
from dature.errors.exceptions import DatureConfigError
from dature.validators.root import RootValidator


class TestRootValidator:
    def test_success(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int
            user: str

        def validate_config(obj: Config) -> bool:
            if obj.port < 1024:
                return obj.user == "root"
            return True

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "user": "root"}')

        metadata = Source(
            file=json_file,
            root_validators=(RootValidator(func=validate_config),),
        )
        result = load(metadata, Config)

        assert result.port == 80
        assert result.user == "root"

    def test_validation_fails(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int
            user: str

        def validate_config(obj: Config) -> bool:
            if obj.port < 1024:
                return obj.user == "root"
            return True

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "user": "admin"}')

        metadata = Source(
            file=json_file,
            root_validators=(RootValidator(func=validate_config),),
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (f"  [<root>]  Root validation failed\n   └── FILE '{json_file}'")

    def test_multiple_root_validators(self, tmp_path: Path):
        @dataclass
        class Config:
            min_value: int
            max_value: int
            step: int

        def validate_min_max(obj: Config) -> bool:
            return obj.min_value < obj.max_value

        def validate_step(obj: Config) -> bool:
            return obj.step > 0

        json_file = tmp_path / "config.json"
        json_file.write_text('{"min_value": 10, "max_value": 100, "step": 5}')

        metadata = Source(
            file=json_file,
            root_validators=(
                RootValidator(func=validate_min_max),
                RootValidator(func=validate_step),
            ),
        )
        result = load(metadata, Config)

        assert result.min_value == 10
        assert result.max_value == 100
        assert result.step == 5

    def test_multiple_root_validators_all_fail(self, tmp_path: Path):
        @dataclass
        class Config:
            min_value: int
            max_value: int
            step: int

        def validate_min_max(obj: Config) -> bool:
            return obj.min_value < obj.max_value

        def validate_step(obj: Config) -> bool:
            return obj.step > 0

        json_file = tmp_path / "config.json"
        json_file.write_text('{"min_value": 100, "max_value": 10, "step": -5}')

        metadata = Source(
            file=json_file,
            root_validators=(
                RootValidator(func=validate_min_max),
                RootValidator(func=validate_step),
            ),
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (f"  [<root>]  Root validation failed\n   └── FILE '{json_file}'")

    def test_root_validator_privileged_port(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int
            host: str

        def validate_config(obj: Config) -> bool:
            return obj.host != "localhost" or obj.port in range(1024, 65536)

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "host": "localhost"}')

        metadata = Source(
            file=json_file,
            root_validators=(RootValidator(func=validate_config),),
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (f"  [<root>]  Root validation failed\n   └── FILE '{json_file}'")

    def test_root_validator_with_decorator(self, tmp_path: Path):
        def validate_credentials(obj) -> bool:
            if obj.username == "admin":
                return len(obj.password) >= 12
            return len(obj.password) >= 8

        json_file = tmp_path / "config.json"
        json_file.write_text('{"username": "admin", "password": "short"}')

        metadata = Source(
            file=json_file,
            root_validators=(RootValidator(func=validate_credentials),),
        )

        @load(metadata)
        @dataclass
        class Credentials:
            username: str
            password: str

        with pytest.raises(DatureConfigError) as exc_info:
            Credentials()

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Credentials loading errors (1)"
        assert str(e.exceptions[0]) == (f"  [<root>]  Root validation failed\n   └── FILE '{json_file}'")

    def test_custom_error_message(self, tmp_path: Path):
        @dataclass
        class Config:
            port: int
            user: str

        def validate_config(obj: Config) -> bool:
            if obj.port < 1024:
                return obj.user == "root"
            return True

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "user": "admin"}')

        metadata = Source(
            file=json_file,
            root_validators=(
                RootValidator(
                    func=validate_config,
                    error_message="Ports below 1024 require root user",
                ),
            ),
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(metadata, Config)

        e = exc_info.value
        assert len(e.exceptions) == 1
        assert str(e) == "Config loading errors (1)"
        assert str(e.exceptions[0]) == (f"  [<root>]  Ports below 1024 require root user\n   └── FILE '{json_file}'")
