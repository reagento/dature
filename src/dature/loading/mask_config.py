from dataclasses import replace

from dature.config import DatureConfig
from dature.type_aliases import MaskingMode


def apply_masking_mode(config: DatureConfig, masking_mode: MaskingMode | None) -> DatureConfig:
    """Return *config* with a per-call ``masking_mode`` override folded into its masking group.

    Args:
        config: The effective config for the load, before the per-call override.
        masking_mode: The per-call override, or ``None`` when the caller did not override.

    Returns:
        *config* unchanged when there is nothing to override, otherwise a copy whose
        ``masking.masking_mode`` is *masking_mode*.
    """
    if masking_mode is None or masking_mode == config.masking.masking_mode:
        return config
    return replace(config, masking=replace(config.masking, masking_mode=masking_mode))
