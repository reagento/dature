Fixed :class:`VaultSource` failing to load ``bytearray`` fields — Vault's native-JSON
payload has no ``bytearray`` representation, and ``RemoteSource`` previously had no
loader for it. Also fixed ``float("inf")``/``float("nan")`` silently staying as strings
instead of coercing to ``float``, since JSON has no native ``Infinity``/``NaN`` literals.
