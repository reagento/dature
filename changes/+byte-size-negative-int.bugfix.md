`ByteSize(-5)` (constructed from an `int`) now raises `ValueError` instead of silently accepting a negative size, matching the string form (`ByteSize("-5B")`), which already rejected negative values.
