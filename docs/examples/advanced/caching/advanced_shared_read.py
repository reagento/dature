import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature

with tempfile.TemporaryDirectory() as tmp_dir:
    config_file = Path(tmp_dir) / "app.yaml"
    config_file.write_text("module1:\n  x: 1\nmodule2:\n  x: 2\n")

    @dataclass
    class Config:
        x: int

    base = dature.Yaml11Source(file=config_file, shared_read=True)

    # The file changes on disk after the first read...
    first = dature.load(base.replace(prefix="module1"), schema=Config)
    config_file.write_text("module1:\n  x: 999\nmodule2:\n  x: 999\n")

    # ...but clones made via .replace() still share base's cached raw read
    second = dature.load(base.replace(prefix="module2"), schema=Config)

    assert first == Config(x=1)
    assert second == Config(x=2)
