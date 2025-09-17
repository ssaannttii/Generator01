from __future__ import annotations

import math
import random

from star_chart_generator.camera import create_projection
from star_chart_generator.config import (
    BackgroundDistribution,
    BulgeDistribution,
    Camera,
    Resolution,
    StarConfig,
)
from star_chart_generator.sampling import generate_star_field, render_star_field


def _average(values: list[float]) -> float:
    return sum(values) / max(len(values), 1)


def test_star_field_distribution():
    resolution = Resolution(width=256, height=256, ssaa=1)
    camera = Camera(pitch_deg=78, fov_deg=35, z_far=6.0)
    config = StarConfig(
        bulge=BulgeDistribution(sigma=0.22, falloff_alpha=1.9, count=200, size_px=(0.8, 2.1)),
        background=BackgroundDistribution(count=150, size_px=(0.5, 1.4), jitter=0.25, min_r=0.45, max_r=1.05),
    )

    projection = create_projection(resolution, camera, [])
    stars = generate_star_field(config, projection, rng=random.Random(1234), ssaa=resolution.ssaa)
    assert len(stars) == config.bulge.count + config.background.count

    image = render_star_field(stars, projection)
    assert image.width == projection.width
    assert image.height == projection.height

    total_light = sum(pixel[channel] for row in image.pixels for pixel in row for channel in range(3))
    assert total_light > 0.0

    cx, cy = projection.center_x, projection.center_y
    core_radii = [math.hypot(star.x - cx, star.y - cy) for star in stars[: config.bulge.count]]
    halo_radii = [math.hypot(star.x - cx, star.y - cy) for star in stars[config.bulge.count :]]

    assert _average(core_radii) < _average(halo_radii)
