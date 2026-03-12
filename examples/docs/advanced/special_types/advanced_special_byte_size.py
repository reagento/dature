"""ByteSize — parses human-readable sizes."""

from dataclasses import dataclass

from dature.fields.byte_size import ByteSize


@dataclass
class Config:
    max_upload: ByteSize


config = Config(max_upload=ByteSize("1.5 GB"))

print(int(config.max_upload))  # 1500000000
print(str(config.max_upload))  # 1.4GiB
print(repr(config.max_upload))  # ByteSize(1500000000)
print(config.max_upload.human_readable())  # 1.4GiB
print(config.max_upload.human_readable(decimal=True))  # 1.5GB
print(ByteSize(1024) > ByteSize(512))  # True
