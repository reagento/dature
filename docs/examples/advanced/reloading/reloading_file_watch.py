import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import dature
from dature import FileWatchTrigger

# --8<-- [start:example]
with tempfile.TemporaryDirectory() as tmp_dir:
    config_file = Path(tmp_dir) / "config.json"
    config_file.write_text('{"port": 6379}')

    reloaded = threading.Event()

    @dature.load(
        dature.JsonSource(file=config_file),
        cache=True,
        reload=FileWatchTrigger(debounce=0.1),
        on_reload=lambda _: reloaded.set(),
    )
    @dataclass
    class CacheConfig:
        port: int

    assert CacheConfig().port == 6379

    config_file.write_text('{"port": 9999}')
    assert reloaded.wait(5.0), "FileWatchTrigger did not fire in time"
    assert CacheConfig().port == 9999
    # --8<-- [end:example]
