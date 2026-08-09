"""Hide dature-internal frames from the tracebacks of dature's own errors."""

from pathlib import Path
from types import TracebackType

_PKG_ROOT = str(Path(__file__).resolve().parent.parent)


def user_frames_only(tb: TracebackType | None) -> TracebackType | None:
    """Rebuild *tb* with the dature-internal tail dropped.

    Frames are copied into fresh ``TracebackType`` objects rather than unlinked in
    place, so the real traceback stays intact for debuggers and error reporters.
    """
    kept: list[TracebackType] = []
    while tb is not None and not tb.tb_frame.f_code.co_filename.startswith(_PKG_ROOT):
        kept.append(tb)
        tb = tb.tb_next

    result: TracebackType | None = None
    for frame in reversed(kept):
        result = TracebackType(result, frame.tb_frame, frame.tb_lasti, frame.tb_lineno)
    return result
