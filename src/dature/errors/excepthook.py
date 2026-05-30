import sys
import traceback
from types import TracebackType

from dature.errors.exceptions import DatureConfigError, DatureError

_previous_excepthook = sys.excepthook


def _dature_excepthook(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> None:
    """Render DatureError without Python's traceback header; delegate the rest."""
    if isinstance(exc, (DatureError, DatureConfigError)):
        traceback.print_exception(exc_type, exc, None)
        return
    _previous_excepthook(exc_type, exc, tb)


sys.excepthook = _dature_excepthook
