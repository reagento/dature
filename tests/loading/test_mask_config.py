import pytest

from dature.config import DatureConfig, MaskingConfig
from dature.loading.mask_config import resolve_masking_mode
from dature.type_aliases import MaskingMode


@pytest.mark.parametrize(
    ("masking_mode", "config_mask_secrets", "config_masking_mode", "expected"),
    [
        ("secrets_only", None, "all", "secrets_only"),
        ("none", True, "all", "none"),
        (None, True, "all", "secrets_only"),
        (None, False, "secrets_only", "none"),
        (None, None, "secrets_only", "secrets_only"),
        (None, None, "none", "none"),
    ],
    ids=[
        "load_level_wins_over_config",
        "load_level_wins_over_deprecated_mask_secrets",
        "deprecated_mask_secrets_true_maps_to_secrets_only",
        "deprecated_mask_secrets_false_maps_to_none",
        "falls_through_to_masking_mode_when_mask_secrets_unset",
        "falls_through_to_masking_mode_none",
    ],
)
def test_resolve_masking_mode(
    monkeypatch: pytest.MonkeyPatch,
    masking_mode: MaskingMode | None,
    config_mask_secrets: bool | None,
    config_masking_mode: MaskingMode,
    expected: MaskingMode,
) -> None:
    fake_config = DatureConfig(
        masking=MaskingConfig(mask_secrets=config_mask_secrets, masking_mode=config_masking_mode),
    )

    monkeypatch.setattr("dature.loading.mask_config.config", fake_config)
    result = resolve_masking_mode(masking_mode=masking_mode)

    assert result == expected
