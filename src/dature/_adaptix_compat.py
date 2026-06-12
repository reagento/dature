"""Pinned re-exports of adaptix internals (adaptix 3.0.0b12).

These symbols are not part of adaptix's public API and may move or be renamed
in any release. They are funneled through this one module so that an adaptix
upgrade only requires fixing imports here, not across the providers. Re-check
every symbol whenever the pinned adaptix version changes.
"""

from adaptix._internal.model_tools.definitions import DefaultValue, InputShape, Param, ParamKind
from adaptix._internal.morphing.model.loader_provider import ModelLoaderProvider
from adaptix._internal.morphing.request_cls import LoaderRequest
from adaptix._internal.provider.essential import RequestHandlerRegisterRecord
from adaptix._internal.provider.located_request import LocatedRequest
from adaptix._internal.provider.request_checkers import AlwaysTrueRequestChecker
from adaptix._internal.provider.shape_provider import InputShapeRequest, provide_generic_resolved_shape

__all__ = [
    "AlwaysTrueRequestChecker",
    "DefaultValue",
    "InputShape",
    "InputShapeRequest",
    "LoaderRequest",
    "LocatedRequest",
    "ModelLoaderProvider",
    "Param",
    "ParamKind",
    "RequestHandlerRegisterRecord",
    "provide_generic_resolved_shape",
]
