"""``FixedIntervalTrigger`` — unconditional reload every N seconds."""

from dature.reloading.base import ReloadTrigger


class FixedIntervalTrigger(ReloadTrigger):
    """Reload unconditionally every *interval*, starting after the first interval elapses.

    See :class:`ReloadTrigger` for the ``interval=``/``scheduler=`` arguments.
    """

    def _poll(self) -> bool:
        return True
