from dature import F

field_ref = F["Config"].name  # autocomplete doesn't work here

assert field_ref is not None
