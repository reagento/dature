import pytest

from dature.config import DatureConfig, MaskingConfig
from dature.loading.common import resolve_mask_secrets


@pytest.mark.parametrize(
    ("load_level", "config_default", "expected"),
    [
        (True, False, True),
        (False, True, False),
        (None, True, True),
        (None, False, False),
    ],
    ids=[
        "load_true_wins",
        "load_false_wins",
        "config_true_default",
        "config_false_default",
    ],
)
def test_resolve_mask_secrets(
    monkeypatch: pytest.MonkeyPatch,
    load_level: bool | None,
    config_default: bool,
    expected: bool,
) -> None:
    fake_config = DatureConfig(masking=MaskingConfig(mask_secrets=config_default))
    monkeypatch.setattr("dature.loading.common.config", fake_config)
    result = resolve_mask_secrets(load_level=load_level)
    assert result == expected
