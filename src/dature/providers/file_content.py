"""Loader provider for ``FileContent`` that reads the mode and ``FileOptions`` from the type hint."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, get_args, get_origin

from adaptix import CannotProvide, Loader, Mediator, Provider
from adaptix.load_error import TypeLoadError

from dature.fields.file_content import FileContent, FileMode, FileOptions
from dature.providers._adaptix_compat import AlwaysTrueRequestChecker, LoaderRequest, RequestHandlerRegisterRecord


def _options_of(request: LoaderRequest) -> FileOptions:
    """Find ``FileOptions`` in the ``Annotated`` hint that adaptix unwrapped just before this request."""
    if len(request.loc_stack) < 2:  # noqa: PLR2004
        return FileOptions()

    outer_type = request.loc_stack[-2].type
    if get_origin(outer_type) is not Annotated:
        return FileOptions()

    return next((meta for meta in get_args(outer_type)[1:] if isinstance(meta, FileOptions)), FileOptions())


class FileContentProvider(Provider):
    """Load ``FileContent``, ``FileContent[bytes]`` and ``Annotated[FileContent, FileOptions(...)]``.

    ``loader()`` is not enough: its function sees only the raw value, not the mode or the options.
    """

    @staticmethod
    def _make_loader(
        _mediator: Mediator[Loader[FileContent[str] | FileContent[bytes]]],
        request: LoaderRequest,
    ) -> Callable[[str], FileContent[str] | FileContent[bytes]]:
        field_type = request.last_loc.type
        origin: object = get_origin(field_type) or field_type
        if origin is not FileContent:
            raise CannotProvide

        mode: FileMode = "rb" if get_args(field_type) == (bytes,) else "r"
        options = _options_of(request)

        def load(value: str) -> FileContent[str] | FileContent[bytes]:
            if not isinstance(value, str):
                raise TypeLoadError(str, value)

            path = Path(value)
            if not path.is_file():
                error = ValueError(f"File not found: {value}")
                error.input_value = value  # type: ignore[attr-defined]
                raise error
            return FileContent(path, options, mode=mode)

        return load

    def get_request_handlers(self) -> Sequence[RequestHandlerRegisterRecord]:
        return [(LoaderRequest, AlwaysTrueRequestChecker(), self._make_loader)]
