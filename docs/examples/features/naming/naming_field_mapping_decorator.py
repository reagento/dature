# --8<-- [start:setup]
from dature import F
# --8<-- [end:setup]

# --8<-- [start:example]
field_ref = F["Config"].name  # autocomplete doesn't work here
# --8<-- [end:example]

assert field_ref is not None
