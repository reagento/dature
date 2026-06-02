"""Decorator mode — use string instead of class reference in F[]."""

from dature import F

# --8<-- [start:decorator]
field_ref = F["Config"].name  # autocomplete doesn't work here
# --8<-- [end:decorator]

assert field_ref is not None
