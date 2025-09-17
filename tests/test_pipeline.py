from __future__ import annotations

import math
from pathlib import Path

import star_chart_generator.labels as label_module
from star_chart_generator import SceneConfig, generate_star_chart
from star_chart_generator.camera import create_projection


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


def _pixel_intensity(pixel) -> float:
    return pixel[0] + pixel[1] + pixel[2]


def _half_max_area(image) -> int:
    max_intensity = 0.0
    for row in image.pixels:
        for pixel in row:
            max_intensity = max(max_intensity, _pixel_intensity(pixel))
    if max_intensity <= 0.0:
        return 0
    threshold = max_intensity * 0.5
    count = 0
    for row in image.pixels:
        for pixel in row:
            if _pixel_intensity(pixel) >= threshold:
                count += 1
    return count


def _label_extent(image, threshold: float = 1e-4) -> tuple[int, int]:
    rows = [
        y
        for y, row in enumerate(image.pixels)
        if sum(_pixel_intensity(pixel) for pixel in row) > threshold
    ]
    cols = [
        x
        for x in range(image.width)
        if sum(_pixel_intensity(image.pixels[y][x]) for y in range(image.height)) > threshold
    ]
    if not rows or not cols:
        return 0, 0
    height = rows[-1] - rows[0] + 1
    width = cols[-1] - cols[0] + 1
    return width, height


def test_generate_star_chart(tmp_path: Path):
    config = SceneConfig.from_dict(
        {
            "seed": 900,
            "resolution": {"width": 256, "height": 256, "ssaa": 1},
            "camera": {"pitch_deg": 82, "fov_deg": 35, "z_far": 6.0},
            "rings": [
                {
                    "r": 0.32,
                    "width": 0.012,
                    "color": "#4384CE",
                    "tick": {"every_deg": [10, 30], "length_px": [8, 14], "alpha": 0.9},
                    "label": "GATEWAY",
                },
                {
                    "r": 0.47,
                    "width": 0.009,
                    "color": "#D27738",
                    "tick": {"every_deg": [5, 15, 45], "length_px": [6, 11]},
                    "label": "ARRAY",
                    "label_angle_deg": 118,
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
                        "offset": 0.04,
                    },
                },
                {
                    "text": "Ω 114",
                    "alignment": "center",
                    "placement": {
                        "type": "linear",
                        "ring": 1,
                        "angle_deg": 36,
                        "offset": 0.015,
                    },
                },
            ],
            "stars": {
                "bulge": {"sigma": 0.2, "falloff_alpha": 1.8, "count": 600, "size_px": [1.0, 2.2]},
                "bg": {"count": 180, "size_px": [0.6, 1.2], "jitter": 0.25},
                "warm_color": "#E8B551",
                "hot_color": "#FFFFFF",
                "background_color": "#CFA05A",
            },
            "text": {"size_px": 20, "color": "#e8f2ff", "tracking": -0.4},
            "post": {
                "bloom": {"threshold": 0.72, "sigma_px": [2.0, 5.0], "intensity": [0.7, 0.3]},
                "chromab": {"pixels": 1.1},
                "anamorphic": {"length_px": 32, "intensity": 0.22},
                "vignette": 0.16,
                "grain": 0.0,
            },
            "hud": {
                "enabled": True,
                "height_px": 120,
                "readouts": [
                    {"text": "ETA 05:12:33", "position": 0.78, "alignment": "end"},
                    {"text": "CORE 0.81", "position": 0.28, "alignment": "start"},
                ],
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
    projection = create_projection(config.resolution, config.camera, config.rings)
    ssaa = max(1, config.resolution.ssaa)
    label_scale = max(1.0, config.text.size_px / 18.0) * ssaa

    for readout in config.readouts:
        placement = readout.placement
        ring = config.rings[placement.ring_index]
        radius_ratio = (
            placement.radius
            if placement.radius is not None
            else ring.r + placement.radial_offset
        )
        center_y, radius_x, radius_y = projection.ellipse_parameters(radius_ratio)
        theta = math.radians(placement.angle_deg)
        advances = label_module._text_advances(readout.text, config.text.tracking)
        arc_length = sum(advances) * label_scale
        effective_radius = max((radius_x + radius_y) * 0.5, 1.0)
        arc_angle = arc_length / effective_radius
        if readout.alignment == "start":
            theta += arc_angle / 2.0
        elif readout.alignment == "end":
            theta -= arc_angle / 2.0
        cx = projection.center_x + radius_x * math.cos(theta)
        cy = center_y + radius_y * math.sin(theta)
        energy = _sample_energy(ui_core, cx, cy, radius=3)
        assert energy > 0.0

    band_height = max(24 * ssaa, int(ssaa * config.resolution.height * 0.08))
    hud_y = config.resolution.height - band_height * 0.4
    hud_energy = _sample_energy(ui_core, projection.center_x, hud_y, radius=6)
    assert hud_energy > 0.0

    output_path = tmp_path / "chart.png"
    result.save(str(output_path))
    assert output_path.exists()


def test_supersampling_consistency():
    def make_config(ssaa: int) -> SceneConfig:
        return SceneConfig.from_dict(
            {
                "seed": 321,
                "resolution": {"width": 64, "height": 64, "ssaa": ssaa},
                "camera": {"pitch_deg": 78, "fov_deg": 33, "z_far": 5.5},
                "rings": [
                    {
                        "r": 0.3,
                        "width": 0.0,
                        "color": "#000000",
                        "halo_color": "#000000",
                    }
                ],
                "readouts": [
                    {
                        "text": "TEST",
                        "alignment": "center",
                        "placement": {
                            "type": "linear",
                            "ring": 0,
                            "angle_deg": 0,
                            "offset": 0.12,
                        },
                    }
                ],
                "stars": {
                    "bulge": {"sigma": 0.08, "falloff_alpha": 1.9, "count": 1, "size_px": [1.2, 1.2]},
                    "bg": {"count": 0, "size_px": [1.0, 1.0], "jitter": 0.0},
                },
                "text": {"size_px": 18, "color": "#ffffff", "tracking": 0.0},
                "post": {
                    "bloom": {"threshold": 0.8, "sigma_px": [4.0], "intensity": [0.0]},
                    "chromab": {"pixels": 0.0},
                    "vignette": 0.0,
                    "grain": 0.0,
                    "anamorphic": {"enabled": False},
                },
                "hud": {"enabled": False},
            }
        )

    base_config = make_config(1)
    supersampled_config = make_config(2)

    base_result = generate_star_chart(base_config, seed=777)
    supersampled_result = generate_star_chart(supersampled_config, seed=777)

    base_star_area = _half_max_area(base_result.layers["stars"])
    supersampled_star_area = _half_max_area(supersampled_result.layers["stars"])
    assert base_star_area == supersampled_star_area

    base_label_extent = _label_extent(base_result.layers["ui_core"])
    supersampled_label_extent = _label_extent(supersampled_result.layers["ui_core"])
    assert base_label_extent == supersampled_label_extent

