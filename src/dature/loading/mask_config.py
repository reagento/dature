from dature.config import config


def resolve_mask_secrets(*, load_level: bool | None = None) -> bool:
    if load_level is not None:
        return load_level
    return config.masking.mask_secrets
