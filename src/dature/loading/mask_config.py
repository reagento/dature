from dature.config import config
from dature.type_aliases import MaskingMode


def resolve_masking_mode(*, masking_mode: MaskingMode | None = None) -> MaskingMode:
    if masking_mode is not None:
        return masking_mode
    cfg = config.masking
    if cfg.mask_secrets is not None:
        return "secrets_only" if cfg.mask_secrets else "none"
    return cfg.masking_mode if cfg.masking_mode is not None else "all"
