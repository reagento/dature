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
        stale_on_error="keep",
    )
    @dataclass
    class KeepConfig:
        port: int

    first = KeepConfig()

    # Source becomes unreadable and the TTL expires.
    config_file.write_text("not valid json")
    time.sleep(1.1)

    # Reload fails, but "keep" falls back to the last good config and
    # restarts the TTL window.
    second = KeepConfig()

    # Source is fixed, but the window was just restarted — no reload yet.
    config_file.write_text('{"port": 9999}')
    third = KeepConfig()

    assert first.port == 6379
    assert second.port == 6379
    assert third.port == 6379

    # Once the restarted window expires, the fixed value loads.
    time.sleep(1.1)
    fourth = KeepConfig()

    assert fourth.port == 9999
