from __future__ import annotations

import math
import random

from star_chart_generator.config import Camera, CoreDistribution, HaloDistribution, Resolution, StarConfig
from star_chart_generator.sampling import generate_star_field, render_star_field


def _average(values: list[float]) -> float:
    return sum(values) / max(len(values), 1)


def test_star_field_distribution():
    resolution = Resolution(width=256, height=256, ssaa=1)
    camera = Camera(tilt_deg=28, fov_deg=35)
    config = StarConfig(
        core=CoreDistribution(sigma=0.22, alpha=3.0, count=200),
        halo=HaloDistribution(count=150, min_r=0.45, max_r=1.05),
        brightness_power=1.6,
        min_size_px=0.6,
        max_size_px=2.2,
    )

    stars = generate_star_field(config, resolution, camera, rng=random.Random(1234))
    assert len(stars) == config.core.count + config.halo.count

    image = render_star_field(stars, resolution)
    assert image.width == resolution.width
    assert image.height == resolution.height

    total_light = sum(pixel[channel] for row in image.pixels for pixel in row for channel in range(3))
    assert total_light > 0.0

    cx, cy = resolution.width / 2.0, resolution.height / 2.0
    ellipse_ratio = camera.ellipse_ratio
    core_radii = []
    for star in stars[: config.core.count]:
        dx = star.x - cx
        dy = (star.y - cy) / ellipse_ratio
        core_radii.append(math.hypot(dx, dy))
    halo_radii = []
    for star in stars[config.core.count :]:
        dx = star.x - cx
        dy = (star.y - cy) / ellipse_ratio
        halo_radii.append(math.hypot(dx, dy))

    assert _average(core_radii) < _average(halo_radii)
