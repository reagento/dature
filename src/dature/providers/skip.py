"""Providers and helpers for ``skip_field_if_invalid``."""

import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from adaptix import Loader, Mediator, Provider, Retort
from adaptix.load_error import LoadError

from dature.nested_dict import collect_not_loaded_paths, remove_path_from_dict
from dature.protocols import DataclassInstance
from dature.providers._adaptix_compat import AlwaysTrueRequestChecker, LoaderRequest, RequestHandlerRegisterRecord
from dature.type_aliases import NOT_LOADED, JSONValue, NotLoaded, ProbeDict


class SkipFieldProvider(Provider):
    @staticmethod
    def _wrap_handler(
        mediator: Mediator[Loader[JSONValue | NotLoaded]],
        _request: LoaderRequest,
    ) -> Callable[[JSONValue], JSONValue | NotLoaded]:
        next_handler = mediator.provide_from_next()

        def chain_handler(data: JSONValue) -> JSONValue | NotLoaded:
            try:
                return cast("JSONValue", next_handler(data))
            except (LoadError, ValueError, TypeError):
                return NOT_LOADED

        return chain_handler

    def get_request_handlers(self) -> Sequence[RequestHandlerRegisterRecord]:
        return [(LoaderRequest, AlwaysTrueRequestChecker(), self._wrap_handler)]


@dataclass(frozen=True, slots=True)
class FilterResult:
    cleaned_dict: JSONValue
    skipped_paths: list[str]


def filter_invalid_fields(
    raw_dict: JSONValue,
    probe_retort: Retort,
    schema: type[DataclassInstance],
    allowed_fields: set[str] | None,
) -> FilterResult:
    if not isinstance(raw_dict, dict):
        return FilterResult(cleaned_dict=raw_dict, skipped_paths=[])

    probed: ProbeDict = probe_retort.load(raw_dict, schema)  # pyright: ignore[reportAssignmentType]
    all_not_loaded = collect_not_loaded_paths(probed, "")

    skipped: list[str] = []
    for path in all_not_loaded:
        if allowed_fields is not None and path not in allowed_fields:
            continue
        skipped.append(path)

    if not skipped:
        return FilterResult(cleaned_dict=raw_dict, skipped_paths=[])

    cleaned: dict[str, JSONValue] = copy.deepcopy(raw_dict)
    for path in skipped:
        remove_path_from_dict(cleaned, path)

    return FilterResult(cleaned_dict=cleaned, skipped_paths=skipped)
