"""Load from file-like objects (BytesIO, StringIO)."""

from dataclasses import dataclass
from io import BytesIO, StringIO

from dature import LoadMetadata, load
from dature.sources_loader.json_ import JsonLoader


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# From StringIO
text_stream = StringIO('{"host": "localhost", "port": 8080, "debug": true}')
config = load(LoadMetadata(file_=text_stream, loader=JsonLoader), Config)

print(f"host: {config.host}")  # host: localhost
print(f"port: {config.port}")  # port: 8080

# From BytesIO
binary_stream = BytesIO(b'{"host": "0.0.0.0", "port": 3000}')
config = load(LoadMetadata(file_=binary_stream, loader=JsonLoader), Config)

print(f"host: {config.host}")  # host: 0.0.0.0
print(f"port: {config.port}")  # port: 3000
