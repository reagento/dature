from dataclasses import asdict, dataclass
from typing import Annotated, Any, ClassVar, TypedDict, cast

from dature.types import NestedResolveStrategy, TypeLoaderMap
from dature.validators.number import Ge
from dature.validators.string import MinLength


# --8<-- [start:masking-config]
@dataclass(frozen=True, slots=True)
class MaskingConfig:
    mask: Annotated[str, MinLength(value=1)] = "<REDACTED>"
    visible_prefix: Annotated[int, Ge(value=0)] = 0
    visible_suffix: Annotated[int, Ge(value=0)] = 0
    min_heuristic_length: Annotated[int, Ge(value=1)] = 8
    heuristic_threshold: float = 0.5
    secret_field_names: tuple[str, ...] = (
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "api_secret",
        "access_key",
        "private_key",
        "auth",
        "credential",
    )
    mask_secrets: bool = True


# --8<-- [end:masking-config]


# --8<-- [start:error-display-config]
@dataclass(frozen=True, slots=True)
class ErrorDisplayConfig:
    max_visible_lines: Annotated[int, Ge(value=1)] = 3
    max_line_length: Annotated[int, Ge(value=1)] = 80


# --8<-- [end:error-display-config]


# --8<-- [start:loading-config]
@dataclass(frozen=True, slots=True)
class LoadingConfig:
    cache: bool = True
    debug: bool = False
    nested_resolve_strategy: NestedResolveStrategy = "flat"


# --8<-- [end:loading-config]


@dataclass(frozen=True, slots=True)
class DatureConfig:
    masking: MaskingConfig = MaskingConfig()
    error_display: ErrorDisplayConfig = ErrorDisplayConfig()
    loading: LoadingConfig = LoadingConfig()


def _load_config() -> DatureConfig:
    from dature.main import load  # noqa: PLC0415
    from dature.metadata import Source  # noqa: PLC0415

    return load(Source(prefix="DATURE_"), dataclass_=DatureConfig)


class MaskingOptions(TypedDict, total=False):
    mask: str
    visible_prefix: int
    visible_suffix: int
    min_heuristic_length: int
    heuristic_threshold: float
    secret_field_names: tuple[str, ...]
    mask_secrets: bool


class ErrorDisplayOptions(TypedDict, total=False):
    max_visible_lines: int
    max_line_length: int


class LoadingOptions(TypedDict, total=False):
    cache: bool
    debug: bool
    nested_resolve_strategy: NestedResolveStrategy


class _ConfigProxy:
    _instance: DatureConfig | None = None
    _loading: bool = False
    _type_loaders: ClassVar[TypeLoaderMap] = {}

    @staticmethod
    def ensure_loaded() -> DatureConfig:
        if _ConfigProxy._instance is not None:
            return _ConfigProxy._instance
        if _ConfigProxy._loading:
            return DatureConfig()
        _ConfigProxy._loading = True
        try:
            _ConfigProxy._instance = _load_config()
        finally:
            _ConfigProxy._loading = False
        return _ConfigProxy._instance

    @staticmethod
    def set_instance(value: DatureConfig | None) -> None:
        _ConfigProxy._instance = value

    @staticmethod
    def set_type_loaders(value: TypeLoaderMap) -> None:
        _ConfigProxy._type_loaders = value

    @property
    def masking(self) -> MaskingConfig:
        return self.ensure_loaded().masking

    @property
    def error_display(self) -> ErrorDisplayConfig:
        return self.ensure_loaded().error_display

    @property
    def loading(self) -> LoadingConfig:
        return self.ensure_loaded().loading

    @property
    def type_loaders(self) -> TypeLoaderMap:
        return _ConfigProxy._type_loaders


config: _ConfigProxy = _ConfigProxy()


# --8<-- [start:configure]
def configure(
    *,
    masking: MaskingOptions | None = None,
    error_display: ErrorDisplayOptions | None = None,
    loading: LoadingOptions | None = None,
    type_loaders: TypeLoaderMap | None = None,
) -> None:
    # --8<-- [end:configure]
    current = config.ensure_loaded()

    merged_masking = (
        MaskingConfig(**cast("dict[str, Any]", asdict(MaskingConfig()) | masking))
        if masking is not None
        else current.masking
    )
    merged_error = (
        ErrorDisplayConfig(**cast("dict[str, Any]", asdict(ErrorDisplayConfig()) | error_display))
        if error_display is not None
        else current.error_display
    )
    merged_loading = (
        LoadingConfig(**cast("dict[str, Any]", asdict(LoadingConfig()) | loading))
        if loading is not None
        else current.loading
    )

    config.set_instance(
        DatureConfig(
            masking=merged_masking,
            error_display=merged_error,
            loading=merged_loading,
        ),
    )
    if type_loaders is not None:
        config.set_type_loaders(type_loaders)
