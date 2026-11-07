from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

from dature import JsonSource, load
from dature.errors import DatureConfigError, FieldLoadError
from dature.fields.file_content import FileContent


class TestFileContentMasking:
    @pytest.mark.parametrize(
        ("masking_mode", "expected_message"),
        [
            ("none", "File not found: {path}"),
            ("all", "File not found: <REDACTED>"),
        ],
        ids=["none", "all"],
    )
    def test_missing_file_error_message_respects_masking_mode(
        self,
        tmp_path: Path,
        masking_mode: Literal["none", "all"],
        expected_message: str,
    ) -> None:
        missing = tmp_path / "missing.txt"
        config_file = tmp_path / "config.json"
        config_file.write_text(f'{{"cert": "{missing.as_posix()}"}}')

        @dataclass
        class Cfg:
            cert: FileContent[str]

        with pytest.raises(DatureConfigError) as exc_info:
            load(JsonSource(file=config_file), masking_mode=masking_mode, schema=Cfg)

        field_error = exc_info.value.exceptions[0]
        assert isinstance(field_error, FieldLoadError)
        assert list(field_error.field_path) == ["cert"]
        assert field_error.message == expected_message.format(path=missing.as_posix())
