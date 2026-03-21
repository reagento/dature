from pathlib import Path
from typing import TYPE_CHECKING, Any

from dature.sources_loader.docker_secrets import DockerSecretsLoader
from dature.sources_loader.env_ import EnvFileLoader, EnvLoader
from dature.sources_loader.ini_ import IniLoader
from dature.sources_loader.json_ import JsonLoader
from dature.types import FILE_LIKE_TYPES, ExpandEnvVarsMode, NestedResolve, NestedResolveStrategy

if TYPE_CHECKING:
    from dature.metadata import LoadMetadata, TypeLoader
    from dature.protocols import LoaderProtocol
    from dature.types import FileLike, FilePath

SUPPORTED_EXTENSIONS = (".cfg", ".env", ".ini", ".json", ".json5", ".toml", ".yaml", ".yml")

_EXTRA_BY_EXTENSION: dict[str, str] = {
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json5": "json5",
}


def _resolve_by_extension(extension: str) -> "type[LoaderProtocol]":
    try:
        return _resolve_by_extension_inner(extension)
    except ImportError:
        extra = _EXTRA_BY_EXTENSION.get(extension)
        if extra is None:
            raise
        msg = f"To use '{extension}' files, install the '{extra}' extra: pip install dature[{extra}]"
        raise ImportError(msg) from None


def _resolve_by_extension_inner(extension: str) -> "type[LoaderProtocol]":
    match extension:
        case ".json":
            return JsonLoader
        case ".toml":
            from dature.sources_loader.toml_ import Toml11Loader  # noqa: PLC0415

            return Toml11Loader
        case ".ini" | ".cfg":
            return IniLoader
        case ".env":
            return EnvFileLoader
        case ".yaml" | ".yml":
            from dature.sources_loader.yaml_ import Yaml12Loader  # noqa: PLC0415

            return Yaml12Loader
        case ".json5":
            from dature.sources_loader.json5_ import Json5Loader  # noqa: PLC0415

            return Json5Loader
        case _:
            supported = ", ".join(SUPPORTED_EXTENSIONS)
            msg = (
                f"Cannot determine loader type for extension '{extension}'. "
                f"Please specify loader explicitly or use a supported extension: {supported}"
            )
            raise ValueError(msg)


def resolve_loader_class(
    loader: "type[LoaderProtocol] | None",
    file_: "FileLike | FilePath | None",
) -> "type[LoaderProtocol]":
    if loader is not None:
        if file_ is not None and not isinstance(file_, FILE_LIKE_TYPES) and loader is EnvLoader:
            msg = (
                "EnvLoader reads from environment variables and does not use files. "
                "Remove file_ or use a file-based loader instead (e.g. EnvFileLoader)."
            )
            raise ValueError(msg)
        if isinstance(file_, FILE_LIKE_TYPES) and loader in (EnvLoader, DockerSecretsLoader):
            msg = (
                f"{loader.__name__} does not support file-like objects. "
                "Use a file-based loader (e.g. JsonLoader, TomlLoader) with file-like objects."
            )
            raise ValueError(msg)
        return loader

    if isinstance(file_, FILE_LIKE_TYPES):
        msg = (
            "Cannot determine loader type for a file-like object. "
            "Please specify loader explicitly (e.g. loader=JsonLoader)."
        )
        raise TypeError(msg)

    if file_ is None:
        return EnvLoader

    # file-like objects are handled above; here file_ is str | Path
    file_path = Path(file_)

    if file_path.is_dir():
        return DockerSecretsLoader

    if file_path.name.startswith(".env"):
        return EnvFileLoader

    return _resolve_by_extension(file_path.suffix.lower())


def resolve_loader(
    metadata: "LoadMetadata",
    *,
    expand_env_vars: ExpandEnvVarsMode | None = None,
    type_loaders: "tuple[TypeLoader, ...]" = (),
    nested_resolve_strategy: NestedResolveStrategy = "flat",
    nested_resolve: NestedResolve | None = None,
) -> "LoaderProtocol":
    loader_class = resolve_loader_class(metadata.loader, metadata.file_)

    resolved_expand = expand_env_vars or metadata.expand_env_vars or "default"

    kwargs: dict[str, Any] = {
        "prefix": metadata.prefix,
        "name_style": metadata.name_style,
        "field_mapping": metadata.field_mapping,
        "root_validators": metadata.root_validators,
        "validators": metadata.validators,
        "expand_env_vars": resolved_expand,
        "type_loaders": type_loaders,
    }

    if issubclass(loader_class, (EnvLoader, DockerSecretsLoader)):
        kwargs["split_symbols"] = metadata.split_symbols
        resolved_strategy = metadata.nested_resolve_strategy or nested_resolve_strategy
        kwargs["nested_resolve_strategy"] = resolved_strategy
        resolved_resolve = metadata.nested_resolve or nested_resolve
        if resolved_resolve is not None:
            kwargs["nested_resolve"] = resolved_resolve

    return loader_class(**kwargs)
