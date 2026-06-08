"""Load from file-like objects (BytesIO, StringIO)."""

from dataclasses import dataclass
from io import BytesIO, StringIO

import dature


# --8<-- [start:schema]
@dataclass
class Config:
    host: str
    port: int
    debug: bool = False
# --8<-- [end:schema]


# --8<-- [start:included-string]
# From StringIO
text_stream = StringIO('{"host": "localhost", "port": 8080, "debug": true}')
config = dature.load(dature.JsonSource(file=text_stream), schema=Config)
# --8<-- [end:included-string]

assert config.host == "localhost"
assert config.port == 8080

# --8<-- [start:included-bytes]
# From BytesIO
binary_stream = BytesIO(b'{"host": "0.0.0.0", "port": 3000}')
config = dature.load(dature.JsonSource(file=binary_stream), schema=Config)
# --8<-- [end:included-bytes]

assert config.host == "0.0.0.0"
assert config.port == 3000
