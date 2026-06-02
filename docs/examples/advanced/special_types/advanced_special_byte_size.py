"""ByteSize — parses human-readable sizes."""

from dataclasses import dataclass

from dature.fields.byte_size import ByteSize


@dataclass
class Config:
    max_upload: ByteSize


config = Config(max_upload=ByteSize("1.5 GB"))

assert int(config.max_upload) == 1500000000
assert str(config.max_upload) == "1.4GiB"
assert repr(config.max_upload) == "ByteSize(1500000000)"
assert config.max_upload.human_readable() == "1.4GiB"
assert config.max_upload.human_readable(decimal=True) == "1.5GB"
assert ByteSize(1024) > ByteSize(512)
