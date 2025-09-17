"""Procedural generation of the stellar field."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import math
import random

from .config import Camera, Resolution, StarConfig
from .image import FloatImage
from .utils import mix_colors

Color = Tuple[float, float, float]


@dataclass
class Star:
    x: float
    y: float
    radius: float
    intensity: float
    color: Color


def _sersic_radius(rng: random.Random, sigma: float, alpha: float) -> float:
    u = max(min(rng.random(), 1.0 - 1e-6), 1e-6)
    value = sigma * (-math.log(1.0 - u)) ** (1.0 / max(alpha, 1e-3))
    return min(max(value, 0.0), 1.0)


def _halo_radius(rng: random.Random, r_min: float, r_max: float) -> float:
    if r_max <= r_min:
        r_max = r_min + 1e-3
    u = rng.random()
    return math.sqrt(u * (r_max * r_max - r_min * r_min) + r_min * r_min)


def _color_from_intensity(intensity: float) -> Color:
    cold = (0.18, 0.65, 1.0)
    hot = (1.0, 0.42, 0.18)
    t = min(max(intensity, 0.0), 1.0)
    return mix_colors(cold, hot, t)


def generate_star_field(
    config: StarConfig,
    resolution: Resolution,
    camera: Camera,
    rng: random.Random,
) -> List[Star]:
    width, height = resolution.supersampled()
    base_radius = min(width, height) * 0.5 * 0.92
    ellipse_ratio = camera.ellipse_ratio
    cx, cy = width / 2.0, height / 2.0

    stars: List[Star] = []

    for _ in range(config.core.count):
        theta = rng.random() * math.tau
        radius = _sersic_radius(rng, config.core.sigma, config.core.alpha)
        intensity = (1.0 - rng.random()) ** (1.0 / config.brightness_power)
        color = _color_from_intensity(intensity)
        size = config.min_size_px + intensity * (config.max_size_px - config.min_size_px)
        rx = base_radius * radius
        ry = rx * ellipse_ratio
        x = cx + rx * math.cos(theta)
        y = cy + ry * math.sin(theta)
        stars.append(Star(x=x, y=y, radius=size, intensity=intensity * 1.35, color=color))

    for _ in range(config.halo.count):
        theta = rng.random() * math.tau
        radius = _halo_radius(rng, config.halo.min_r, config.halo.max_r)
        intensity = (1.0 - rng.random()) ** (1.0 / (config.brightness_power + 0.4))
        color = _color_from_intensity(intensity * 0.8)
        size = config.min_size_px * 0.75 + intensity * (config.max_size_px - config.min_size_px)
        rx = base_radius * radius
        ry = rx * ellipse_ratio
        x = cx + rx * math.cos(theta)
        y = cy + ry * math.sin(theta)
        stars.append(Star(x=x, y=y, radius=size, intensity=intensity, color=color))

    return stars


def render_star_field(stars: List[Star], resolution: Resolution) -> FloatImage:
    width, height = resolution.supersampled()
    image = FloatImage.new(width, height, 0.0)
    for star in stars:
        sigma = max(0.5, star.radius / 2.0)
        image.add_gaussian(star.x, star.y, sigma, star.intensity, star.color)
    return image


def downsample(image: FloatImage, factor: int) -> FloatImage:
    return image.downsample(factor)


__all__ = ["Star", "generate_star_field", "render_star_field", "downsample"]
