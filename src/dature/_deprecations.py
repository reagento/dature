"""Backward-compatibility shims for names/behaviors renamed or tightened in 1.0.

Every shim here emits a ``DeprecationWarning`` and will be removed in dature 1.2.
Keep this module private (``_``-prefixed) — it is not part of the public API.
"""

import warnings
from typing import Any, Final, cast

from dature.field_path import F
from dature.type_aliases import MaskingMode, SkipFieldsInvalid

#: Sentinel for "argument not passed" — distinct from ``None``, which is a valid
#: value for ``skip_field_if_invalid``/``skip_invalid_fields``.
UNSET: Final[Any] = object()

REMOVAL_NOTICE = "Support will be removed in dature 1.2."
REMOVAL_NOTICE_13 = "Support will be removed in dature 1.3."

MASK_SECRETS_DEPRECATION_MESSAGE = (
    "`mask_secrets` is deprecated; use `masking_mode` instead "
    f'(`True` -> "secrets_only", `False` -> "none"). {REMOVAL_NOTICE_13}'
)


def resolve_renamed_skip(skip_field_if_invalid: Any, skip_invalid_fields: Any) -> Any:  # noqa: ANN401
    """Merge the deprecated ``skip_invalid_fields`` alias into ``skip_field_if_invalid``.

    Warns and raises if both the new and the deprecated argument are set.
    """
    if skip_invalid_fields is UNSET:
        return skip_field_if_invalid
    warnings.warn(
        f"`skip_invalid_fields` is deprecated; use `skip_field_if_invalid` instead. {REMOVAL_NOTICE}",
        DeprecationWarning,
        stacklevel=3,
    )
    if skip_field_if_invalid is not None:
        msg = "pass only one of `skip_invalid_fields` / `skip_field_if_invalid`, not both"
        raise TypeError(msg)
    return skip_invalid_fields


def normalize_skip_bool(value: Any) -> SkipFieldsInvalid:  # noqa: ANN401
    """Map a deprecated ``bool`` value for ``skip_field_if_invalid`` to its sentinel form.

    ``True`` becomes ``F.ANY`` (skip any invalid field), ``False`` becomes ``None``
    (skip nothing). Non-bool values pass through unchanged.
    """
    if isinstance(value, bool):
        warnings.warn(
            "passing a bool to `skip_field_if_invalid` is deprecated; use `F.ANY` "
            f"(was `True`), or `None` / an empty sequence (was `False`). {REMOVAL_NOTICE}",
            DeprecationWarning,
            stacklevel=3,
        )
        return F.ANY if value else None
    return cast("SkipFieldsInvalid", value)


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
