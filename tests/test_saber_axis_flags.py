"""Tests for saber axis todo presets."""

import config
from saber_axis_flags import apply_axis_preset, list_axis_presets


def test_list_presets_includes_baseline_and_all():
    names = list_axis_presets()
    assert "baseline" in names
    assert "all" in names
    assert "1_color_roi" in names


def test_apply_baseline_clears_flags():
    config.SABER_AXIS_COLOR_ROI = True
    enabled = apply_axis_preset("baseline")
    assert enabled == []
    assert config.SABER_AXIS_COLOR_ROI is False
    assert config.SABER_AXIS_PRESET == "baseline"


def test_apply_all_enables_stack():
    apply_axis_preset("baseline")
    enabled = apply_axis_preset("all")
    assert config.SABER_AXIS_COLOR_ROI is True
    assert config.SABER_AXIS_COLOR_EACH_FRAME is True
    assert config.SABER_AXIS_TEMPORAL is True
    assert config.SABER_FUSE_REQUIRE_TIP_IN_FRAME is True
    assert len(enabled) >= 4
