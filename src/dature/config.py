from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from dature.validators.number import Ge
from dature.validators.string import MaxLength, MinLength

if TYPE_CHECKING:
    from dature.metadata import TypeLoader


# --8<-- [start:masking-config]
@dataclass(frozen=True, slots=True)
class MaskingConfig:
    mask_char: Annotated[str, MinLength(value=1), MaxLength(value=1)] = "*"
    min_visible_chars: Annotated[int, Ge(value=1)] = 2
    min_length_for_partial_mask: Annotated[int, Ge(value=1)] = 5
    fixed_mask_length: Annotated[int, Ge(value=1)] = 5
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


# --8<-- [end:loading-config]


@dataclass(frozen=True, slots=True)
class DatureConfig:
    masking: MaskingConfig = MaskingConfig()
    error_display: ErrorDisplayConfig = ErrorDisplayConfig()
    loading: LoadingConfig = LoadingConfig()


def _load_config() -> DatureConfig:
    from dature.main import load  # noqa: PLC0415
    from dature.metadata import LoadMetadata  # noqa: PLC0415

    return load(LoadMetadata(prefix="DATURE_"), DatureConfig)


class _ConfigProxy:
    _instance: DatureConfig | None = None
    _loading: bool = False
    _type_loaders: "tuple[TypeLoader, ...]" = ()

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
    def set_type_loaders(value: "tuple[TypeLoader, ...]") -> None:
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
    def type_loaders(self) -> "tuple[TypeLoader, ...]":
        return _ConfigProxy._type_loaders


config: _ConfigProxy = _ConfigProxy()


# --8<-- [start:configure]
def configure(
    *,
    masking: MaskingConfig | None = None,
    error_display: ErrorDisplayConfig | None = None,
    loading: LoadingConfig | None = None,
    type_loaders: "tuple[TypeLoader, ...] | None" = None,
) -> None:
    # --8<-- [end:configure]
    current = config.ensure_loaded()
    if masking is None:
        masking = current.masking
    if error_display is None:
        error_display = current.error_display
    if loading is None:
        loading = current.loading
    config.set_instance(
        DatureConfig(
            masking=masking,
            error_display=error_display,
            loading=loading,
        ),
    )
    if type_loaders is not None:
        config.set_type_loaders(type_loaders)
