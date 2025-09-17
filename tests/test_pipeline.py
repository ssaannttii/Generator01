from __future__ import annotations

import math
from pathlib import Path

import star_chart_generator.labels as label_module
from star_chart_generator import SceneConfig, generate_star_chart


def _sample_energy(image, x: float, y: float, radius: int = 3) -> float:
    total = 0.0
    xi = int(round(x))
    yi = int(round(y))
    for dy in range(-radius, radius + 1):
        py = yi + dy
        if py < 0 or py >= image.height:
            continue
        row = image.pixels[py]
        for dx in range(-radius, radius + 1):
            px = xi + dx
            if px < 0 or px >= image.width:
                continue
            pixel = row[px]
            total += pixel[0] + pixel[1] + pixel[2]
    return total


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
            "readouts": [
                {
                    "text": "ENERGY 72%",
                    "alignment": "end",
                    "placement": {
                        "type": "arc",
                        "ring": 0,
                        "angle_deg": 220,
                        "offset": 0.035,
                    },
                },
                {
                    "text": "Ω 114",
                    "alignment": "center",
                    "placement": {
                        "type": "linear",
                        "ring": 1,
                        "angle_deg": 32,
                        "offset": 0.012,
                    },
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

    ui_core = result.layers["ui_core"]
    base_radius = min(config.resolution.width, config.resolution.height) * 0.5 * 0.92
    ellipse_ratio = config.camera.ellipse_ratio
    label_scale = max(1.0, config.text.size_px / (7 * 2.0))

    for readout in config.readouts:
        placement = readout.placement
        ring = config.rings[placement.ring_index]
        radius_ratio = (
            placement.radius
            if placement.radius is not None
            else ring.r + placement.radial_offset
        )
        rx = base_radius * radius_ratio
        ry = rx * ellipse_ratio
        theta = math.radians(placement.angle_deg)
        advances = label_module._text_advances(readout.text, config.text.tracking)
        arc_length = sum(advances) * label_scale
        effective_radius = max((rx + ry) * 0.5, 1.0)
        arc_angle = arc_length / effective_radius
        if readout.alignment == "start":
            theta += arc_angle / 2.0
        elif readout.alignment == "end":
            theta -= arc_angle / 2.0
        cx = config.resolution.width / 2.0 + rx * math.cos(theta)
        cy = config.resolution.height / 2.0 + ry * math.sin(theta)
        energy = _sample_energy(ui_core, cx, cy, radius=3)
        assert energy > 0.0

    output_path = tmp_path / "chart.png"
    result.save(str(output_path))
    assert output_path.exists()
