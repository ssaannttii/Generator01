from __future__ import annotations

from pathlib import Path

from star_chart_generator import SceneConfig, generate_star_chart


def test_generate_star_chart(tmp_path: Path):
    config = SceneConfig.from_dict(
        {
            "seed": 900,
            "resolution": {"width": 256, "height": 256, "ssaa": 1},
            "camera": {"tilt_deg": 30, "fov_deg": 35},
            "rings": [
                {
                    "r": 0.32,
                    "width": 0.01,
                    "color": "#1E90FF",
                    "ticks_every_deg": 15,
                    "label": "GATEWAY",
                },
                {
                    "r": 0.45,
                    "width": 0.008,
                    "color": "#FF6A00",
                    "dash": [10, 4],
                    "ticks_every_deg": 20,
                    "label": "ARRAY",
                    "label_angle_deg": 120,
                },
            ],
            "stars": {
                "core": {"sigma": 0.2, "alpha": 3.1, "count": 200},
                "halo": {"count": 120, "min_r": 0.4, "max_r": 1.0},
                "brightness_power": 1.7,
                "min_size_px": 0.5,
                "max_size_px": 2.0,
            },
            "text": {"size_px": 20, "color": "#e8f2ff", "tracking": -0.5},
            "post": {
                "bloom": {"threshold": 0.85, "intensity": 0.32, "radius": 12},
                "chromatic_aberration": {"k": 0.0015},
                "vignette": 0.12,
                "grain": 0.0,
            },
        }
    )

    result = generate_star_chart(config, seed=123)
    assert result.image.width == config.resolution.width
    assert result.image.height == config.resolution.height
    assert set(result.layers.keys()) >= {"stars", "ui_core", "ui_glow", "final_linear"}

    total_light = sum(channel for row in result.image.pixels for pixel in row for channel in pixel)
    assert total_light > 0.0

    output_path = tmp_path / "chart.png"
    result.save(str(output_path))
    assert output_path.exists()
