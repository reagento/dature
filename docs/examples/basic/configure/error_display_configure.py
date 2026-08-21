# --8<-- [start:example]
import tempfile
from dataclasses import dataclass
from pathlib import Path

import dature
from dature.errors import DatureConfigError


@dataclass
class Settings:
    port: int


narrow = dature.Dature(
    masking={"masking_mode": "none"}, error_display={"max_line_length": 40}
)
wide = dature.Dature(
    masking={"masking_mode": "none"}, error_display={"max_line_length": 200}
)

with tempfile.TemporaryDirectory() as tmpdir:
    config_file = Path(tmpdir) / "config.json"
    config_file.write_text('{"port": "' + "x" * 100 + '"}')

    narrow_message = wide_message = ""

    try:
        narrow.load(dature.JsonSource(file=config_file), schema=Settings)
    except DatureConfigError as exc:
        narrow_message = str(exc.exceptions[0])

    try:
        wide.load(dature.JsonSource(file=config_file), schema=Settings)
    except DatureConfigError as exc:
        wide_message = str(exc.exceptions[0])

# Same failure, rendered differently per instance
assert narrow_message.splitlines()[1].strip().endswith("...")
assert not wide_message.splitlines()[1].strip().endswith("...")
# --8<-- [end:example]
