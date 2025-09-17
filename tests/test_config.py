from __future__ import annotations

import math

import pytest

from star_chart_generator import QualityPreset, SceneConfig


def _make_config() -> SceneConfig:
    return SceneConfig.from_dict(
        {
            "seed": 42,
            "resolution": {"width": 1024, "height": 768, "ssaa": 2},
            "camera": {"pitch_deg": 80, "fov_deg": 35, "z_far": 6.0},
            "rings": [
                {
                    "r": 0.3,
                    "width": 0.012,
                    "color": "#44aaff",
                }
            ],
            "stars": {
                "bulge": {
                    "sigma": 0.18,
                    "falloff_alpha": 1.7,
                    "count": 3200,
                    "size_px": [1.0, 2.2],
                },
                "background": {
                    "count": 1400,
                    "size_px": [0.6, 1.4],
                    "min_r": 0.2,
                    "max_r": 1.0,
                },
            },
            "hud": {"enabled": True, "height_px": 160, "readouts": []},
        }
    )


def test_quality_preview_reduces_workload():
    config = _make_config()
    preview = config.with_quality("preview")

    assert preview.resolution.width < config.resolution.width
    assert preview.resolution.height < config.resolution.height
    assert preview.resolution.ssaa == 1
    assert preview.stars.bulge.count < config.stars.bulge.count
    assert preview.stars.background.count < config.stars.background.count
    assert preview.post.anamorphic.enabled is False
    assert preview.post.chromatic_aberration.pixels <= config.post.chromatic_aberration.pixels
    assert preview.post.grain <= config.post.grain
    assert len(preview.post.bloom.sigmas) <= len(config.post.bloom.sigmas)
    assert preview.text.size_px < config.text.size_px
    assert preview.hud.height_px <= config.hud.height_px


def test_quality_draft_balances_quality_levels():
    config = _make_config()
    draft = config.with_quality(QualityPreset.DRAFT)
    preview = config.with_quality(QualityPreset.PREVIEW)

    assert draft.resolution.width < config.resolution.width
    assert draft.resolution.width > preview.resolution.width
    assert draft.stars.bulge.count > preview.stars.bulge.count
    assert draft.post.anamorphic.enabled is True
    assert draft.post.anamorphic.intensity < config.post.anamorphic.intensity


def test_quality_final_is_identity():
    config = _make_config()
    assert config.with_quality("final") is config


def test_quality_invalid_raises():
    config = _make_config()
    with pytest.raises(ValueError):
        config.with_quality("invalid")


def _base_scene(**overrides):
    base = {
        "seed": 1,
        "resolution": {"width": 320, "height": 240, "ssaa": 1},
        "rings": [
            {
                "r": 0.3,
                "width": 0.01,
                "color": "#ffffff",
            }
        ],
        "stars": {
            "bulge": {
                "sigma": 0.18,
                "falloff_alpha": 1.7,
                "count": 500,
                "size_px": [1.0, 2.0],
            },
            "background": {
                "count": 200,
                "size_px": [0.6, 1.2],
                "min_r": 0.2,
                "max_r": 1.0,
            },
        },
    }
    base.update(overrides)
    return base


def test_camera_accepts_ellipse_ratio():
    config = SceneConfig.from_dict(
        _base_scene(camera={"ellipse_ratio": 0.82, "yaw_deg": 12.0})
    )

    expected_pitch = math.degrees(math.acos(0.82))
    assert math.isclose(config.camera.pitch_deg, expected_pitch, rel_tol=1e-6)
    assert math.isclose(config.camera.ellipse_ratio, 0.82, rel_tol=1e-6)


def test_explicit_empty_hud_disables_defaults():
    config = SceneConfig.from_dict(_base_scene(hud={"readouts": []}))

    assert config.hud.enabled is False
    assert config.hud.readouts == ()
    assert config.hud.use_default_readouts is False


def test_missing_hud_section_uses_defaults():
    config = SceneConfig.from_dict(_base_scene())

    assert config.hud.enabled is True
    assert config.hud.use_default_readouts is True
