from dataclasses import replace

import pytest

from dature.config import DatureConfig, MaskingConfig
from dature.loading.mask_config import apply_masking_mode
from dature.type_aliases import MaskingMode


@pytest.mark.parametrize(
    ("masking_mode", "config_masking_mode", "expected"),
    [
        ("secrets_only", "all", "secrets_only"),
        (None, "secrets_only", "secrets_only"),
        (None, "none", "none"),
    ],
    ids=[
        "override_wins_over_config",
        "no_override_keeps_secrets_only",
        "no_override_keeps_none",
    ],
)
def test_apply_masking_mode_resolves_effective_mode(
    masking_mode: MaskingMode | None,
    config_masking_mode: MaskingMode,
    expected: MaskingMode,
) -> None:
    config = DatureConfig(masking=MaskingConfig(masking_mode=config_masking_mode))

    result = apply_masking_mode(config, masking_mode)

    assert result.masking.masking_mode == expected


@pytest.mark.parametrize(
    "masking_mode",
    [None, "all"],
    ids=["override_is_none", "override_matches_current_mode"],
)
def test_apply_masking_mode_returns_same_config_when_nothing_to_override(masking_mode: MaskingMode | None) -> None:
    config = DatureConfig(masking=MaskingConfig(masking_mode="all"))

    result = apply_masking_mode(config, masking_mode)

    assert result is config


def test_apply_masking_mode_does_not_mutate_the_original_config() -> None:
    config = DatureConfig(masking=MaskingConfig(masking_mode="all"))

    result = apply_masking_mode(config, "secrets_only")

    assert result is not config
    assert result.masking is not config.masking
    assert config.masking.masking_mode == "all"
    assert result == replace(config, masking=replace(config.masking, masking_mode="secrets_only"))
