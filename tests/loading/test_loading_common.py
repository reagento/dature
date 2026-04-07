import pytest

from dature.config import DatureConfig, MaskingConfig
from dature.loading.common import resolve_mask_secrets


@pytest.mark.parametrize(
    ("source_level", "load_level", "config_default", "expected"),
    [
        (True, None, False, True),
        (False, None, True, False),
        (True, False, False, True),
        (None, True, False, True),
        (None, False, True, False),
        (None, None, True, True),
        (None, None, False, False),
    ],
    ids=[
        "source_true_wins",
        "source_false_wins",
        "source_beats_load",
        "load_true_wins",
        "load_false_wins",
        "config_true_default",
        "config_false_default",
    ],
)
def test_resolve_mask_secrets(
    monkeypatch: pytest.MonkeyPatch,
    source_level: bool | None,
    load_level: bool | None,
    config_default: bool,
    expected: bool,
) -> None:
    fake_config = DatureConfig(masking=MaskingConfig(mask_secrets=config_default))
    monkeypatch.setattr("dature.loading.common.config", fake_config)
    result = resolve_mask_secrets(source_level=source_level, load_level=load_level)
    assert result == expected
