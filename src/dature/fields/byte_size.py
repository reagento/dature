import re
from typing import ClassVar


class ByteSize:
    __slots__ = ("_bytes",)

    _UNITS: ClassVar[dict[str, int]] = {
        "b": 1,
        "kb": 10**3,
        "mb": 10**6,
        "gb": 10**9,
        "tb": 10**12,
        "pb": 10**15,
        "kib": 2**10,
        "mib": 2**20,
        "gib": 2**30,
        "tib": 2**40,
        "pib": 2**50,
    }

    _PARSE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*$",
    )

    def __init__(self, value: int | str) -> None:
        if isinstance(value, int):
            if value < 0:
                msg = f"Byte size cannot be negative: {value!r}"
                raise ValueError(msg)
            self._bytes = value
        else:
            self._bytes = self._parse(value)

    @staticmethod
    def _parse(value: str) -> int:
        match = ByteSize._PARSE_RE.match(value)
        if match is None:
            msg = f"Invalid byte size format: {value!r}"
            raise ValueError(msg)

        number_str = match.group(1)
        unit_str = match.group(2).lower()

        if unit_str == "":
            unit_str = "b"

        if unit_str not in ByteSize._UNITS:
            msg = f"Unknown unit: {unit_str!r}"
            raise ValueError(msg)

        multiplier = ByteSize._UNITS[unit_str]
        return int(float(number_str) * multiplier)

    def human_readable(self, *, decimal: bool = False) -> str:
        if decimal:
            units = [("PB", 10**15), ("TB", 10**12), ("GB", 10**9), ("MB", 10**6), ("KB", 10**3)]
        else:
            units = [("PiB", 2**50), ("TiB", 2**40), ("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10)]

        for unit_name, threshold in units:
            if self._bytes >= threshold:
                size = self._bytes / threshold
                if size == int(size):
                    return f"{int(size)}{unit_name}"
                return f"{size:.1f}{unit_name}"

        return f"{self._bytes}B"

    def __int__(self) -> int:
        return self._bytes

    def __str__(self) -> str:
        return self.human_readable()

    def __repr__(self) -> str:
        return f"ByteSize({self._bytes})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ByteSize):
            return NotImplemented
        return self._bytes == other._bytes

    def __hash__(self) -> int:
        return hash(self._bytes)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ByteSize):
            return NotImplemented
        return self._bytes < other._bytes

    def __le__(self, other: object) -> bool:
        if not isinstance(other, ByteSize):
            return NotImplemented
        return self._bytes <= other._bytes

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ByteSize):
            return NotImplemented
        return self._bytes > other._bytes

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, ByteSize):
            return NotImplemented
        return self._bytes >= other._bytes
