import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from dature.fields.file_content import FileContent, FileOptions

with tempfile.TemporaryDirectory() as tmp:
    password_file = Path(tmp) / "db_password"
    password_file.write_text("my-database-password\n", encoding="utf-8")
    cert_file = Path(tmp) / "cert.der"
    cert_file.write_bytes(b"\x00\x01\x02")

    @dataclass
    class Config:
        # Remove the ignore when min Python is 3.13 (PEP 696 default)
        password: FileContent  # type: ignore[type-arg]
        stripped_password: Annotated[FileContent[str], FileOptions(strip=True)]
        cert: FileContent[bytes]

    config = Config(
        password=FileContent(password_file),
        stripped_password=FileContent(password_file, FileOptions(strip=True)),
        cert=FileContent(cert_file, mode="rb"),
    )

    assert config.password.path == password_file
    assert config.password.data == "my-database-password\n"
    assert config.stripped_password.data == "my-database-password"
    assert config.cert.data == b"\x00\x01\x02"
    assert repr(config.password) == f"FileContent(path={str(password_file)!r})"
