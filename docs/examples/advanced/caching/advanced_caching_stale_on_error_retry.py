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
        stale_on_error="retry",
    )
    @dataclass
    class RetryConfig:
        port: int

    first = RetryConfig()

    # Source becomes unreadable and the TTL expires.
    config_file.write_text("not valid json")
    time.sleep(1.1)

    # Reload fails, "retry" falls back to the last good config but leaves
    # the TTL window as-is — the next call retries the reload right away.
    second = RetryConfig()

    # Source is fixed — no need to wait out a window, the very next call
    # reloads immediately.
    config_file.write_text('{"port": 9999}')
    third = RetryConfig()

    assert first.port == 6379
    assert second.port == 6379
    assert third.port == 9999
