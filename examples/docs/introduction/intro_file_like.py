"""Load from file-like objects (BytesIO, StringIO)."""

from dataclasses import dataclass
from io import BytesIO, StringIO

import dature
from dature.sources_loader.json_ import JsonLoader


@dataclass
class Config:
    host: str
    port: int
    debug: bool = False


# From StringIO
text_stream = StringIO('{"host": "localhost", "port": 8080, "debug": true}')
config = dature.load(dature.Source(file=text_stream, loader=JsonLoader), dataclass_=Config)

assert config.host == "localhost"
assert config.port == 8080

# From BytesIO
binary_stream = BytesIO(b'{"host": "0.0.0.0", "port": 3000}')
config = dature.load(dature.Source(file=binary_stream, loader=JsonLoader), dataclass_=Config)

assert config.host == "0.0.0.0"
assert config.port == 3000
