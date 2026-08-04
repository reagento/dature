"""Public namespace for dature base source classes.

Import from here when *extending* dature with a custom source::

    from dature.sources.base import Source, FileSource, CliSource, RemoteSource
    from dature.sources.base import SourceProtocol
"""

from dature.sources.base.cli import CliSource
from dature.sources.base.file import FileFieldMixin, FileSource
from dature.sources.base.flat_key import FlatKeySource
from dature.sources.base.remote import RemoteSource
from dature.sources.base.source import (
    IndexedSource,
    Source,
    bytes_value_loaders,
    clone_source,
    string_value_loaders,
)
from dature.sources.protocol import SourceProtocol

__all__ = [
    "CliSource",
    "FileFieldMixin",
    "FileSource",
    "FlatKeySource",
    "IndexedSource",
    "RemoteSource",
    "Source",
    "SourceProtocol",
    "bytes_value_loaders",
    "clone_source",
    "string_value_loaders",
]
