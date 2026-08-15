import tempfile
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import dature

with tempfile.TemporaryDirectory() as tmp_dir:
    config_file = Path(tmp_dir) / "config.json"
    config_file.write_text('{"port": 6379}')

    @dature.load(
        dature.JsonSource(file=config_file),
        cache=timedelta(seconds=1),
        stale_on_error="raise",
    )
    @dataclass
    class RaiseConfig:
        port: int

    first = RaiseConfig()
    assert first.port == 6379

    # Source becomes unreadable and the TTL expires.
    config_file.write_text("not valid json")
    time.sleep(1.1)

    # "raise" propagates the reload error instead of falling back to the
    # last good config — dature's behavior before stale_on_error existed.
    RaiseConfig()  # Failed
