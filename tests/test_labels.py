from __future__ import annotations

import math

from star_chart_generator.config import TextConfig
from star_chart_generator.labels import LabelSpec, draw_label_layers, layout_labels


def _angle_diff(a: float, b: float) -> float:
    return ((a - b + math.pi) % (2 * math.pi)) - math.pi


def test_label_layout_resolves_collisions():
    text_config = TextConfig(size_px=24, tracking=-0.4)
    center = (320.0, 260.0)
    scale = max(1.0, text_config.size_px / (7 * 2.0))
    specs = [
        LabelSpec(
            ring_index=0,
            text="ALPHA QUADRANT",
            center=center,
            radius_x=190.0,
            radius_y=140.0,
            initial_angle=math.pi / 2,
            tracking=text_config.tracking,
            scale=scale,
        ),
        LabelSpec(
            ring_index=0,
            text="BETA QUADRANT",
            center=center,
            radius_x=190.0,
            radius_y=140.0,
            initial_angle=math.pi / 2 + 0.08,
            tracking=text_config.tracking,
            scale=scale,
        ),
        LabelSpec(
            ring_index=0,
            text="GAMMA",
            center=center,
            radius_x=190.0,
            radius_y=140.0,
            initial_angle=math.pi / 2 - 0.06,
            tracking=text_config.tracking,
            scale=scale,
        ),
    ]

    placements = layout_labels(specs)
    assert len(placements) == len(specs)

    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a = placements[i]
            b = placements[j]
            diff = abs(_angle_diff(a.theta, b.theta))
            required = (a.arc_angle + b.arc_angle) / 2 + 0.05
            assert diff + 1e-3 >= required

    core, glow = draw_label_layers((640, 520), placements, text_config)
    core_energy = sum(channel for row in core.pixels for pixel in row for channel in pixel)
    glow_energy = sum(channel for row in glow.pixels for pixel in row for channel in pixel)
    assert core_energy > 0.0
    assert glow_energy > 0.0
