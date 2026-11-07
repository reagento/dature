import tempfile
from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"

# Prepare config with absolute paths (outside the example section)
config_file = SOURCES_DIR / "advanced_special_file_content.json"
config_template = config_file.read_text()

config_with_paths = config_template.replace("/app/secrets", str(SOURCES_DIR))
with tempfile.NamedTemporaryFile(
    mode="w",
    suffix=".json",
    delete=False,
    delete_on_close=False,
) as f:
    f.write(config_with_paths)
    config_file = Path(f.name)

# --8<-- [start:example]
from dataclasses import dataclass
from typing import Annotated

import dature
from dature.fields.file_content import FileContent, FileOptions


@dataclass
class Config:
    # Remove the ignore when min Python is 3.13 (PEP 696 default)
    password: FileContent  # type: ignore[type-arg]
    stripped_password: Annotated[FileContent[str], FileOptions(strip=True)]
    raw_bytes: FileContent[bytes]


config = dature.load(
    dature.JsonSource(file=config_file),
    schema=Config,
)

assert config.password.data == "my-database-password\n"
assert config.stripped_password.data == "my-database-password"
assert config.raw_bytes.data == b"my-database-password\n"
assert str(config.password.path).endswith("db_password.txt")
# --8<-- [end:example]
