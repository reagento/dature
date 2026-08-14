"""Backward-compatibility shims for names/behaviors renamed or tightened in 1.0.

Keep this module private (``_``-prefixed) — it is not part of the public API.
"""

import warnings

from dature.type_aliases import MaskingMode

REMOVAL_NOTICE_13 = "Support will be removed in dature 1.3."

MASK_SECRETS_DEPRECATION_MESSAGE = (
    "`mask_secrets` is deprecated; use `masking_mode` instead "
    f'(`True` -> "secrets_only", `False` -> "none"). {REMOVAL_NOTICE_13}'
)


def resolve_deprecated_mask_secrets(
    masking_mode: MaskingMode | None,
    mask_secrets: bool | None,  # noqa: FBT001
) -> MaskingMode | None:
    """Map the deprecated ``mask_secrets`` flag onto ``masking_mode``.

    An explicit ``masking_mode`` wins; ``mask_secrets`` is then ignored but still warns.
    """
    if mask_secrets is None:
        return masking_mode
    warnings.warn(MASK_SECRETS_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=3)
    if masking_mode is not None:
        return masking_mode
    return "secrets_only" if mask_secrets else "none"
