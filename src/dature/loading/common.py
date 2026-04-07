from dature.config import config


def resolve_mask_secrets(*, source_level: bool | None = None, load_level: bool | None = None) -> bool:
    if source_level is not None:
        return source_level
    if load_level is not None:
        return load_level
    return config.masking.mask_secrets
