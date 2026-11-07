from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from dature import JsonSource, load
from dature.fields.file_content import FileContent
from dature.validators.v import V


class TestFileContentLoad:
    def test_not_converted_to_dict_when_other_field_has_annotated_validator(self, tmp_path: Path) -> None:
        secret = tmp_path / "secret.txt"
        secret.write_text("value", encoding="utf-8")
        config_file = tmp_path / "config.json"
        config_file.write_text(f'{{"cert": "{secret.as_posix()}", "port": 8080}}')

        @dataclass
        class Cfg:
            cert: FileContent[str]
            port: Annotated[int, V.check(lambda value: value > 0, error_message="port must be positive")]

        result = load(JsonSource(file=config_file), schema=Cfg)

        assert result.cert.path == secret
        assert result.cert.data == "value"
        assert result.port == 8080
