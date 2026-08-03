Fixed error messages for :class:`VaultSource` and :class:`ConsulSource` never showing the
remote address/path of the failing key. ``format_location()`` built the location's content
line (address + field/value) and then discarded it whenever the location had no file path or
env var name — which is always the case for remote sources.
