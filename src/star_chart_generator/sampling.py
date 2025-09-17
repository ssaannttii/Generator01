"""Procedural generation of the stellar field."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import math
import random

from .camera import ProjectionParams
from .config import BackgroundDistribution, BulgeDistribution, StarConfig
from .image import FloatImage
from .utils import clamp, hex_to_rgb, mix_colors

Color = Tuple[float, float, float]


@dataclass
class Star:
    x: float
    y: float
    radius: float
    intensity: float
    color: Color


def _sample_bulge_radius(
    rng: random.Random, sigma: float, alpha: float
) -> float:
    """Sample a radius following an inverse-power falloff."""

    sigma = max(sigma, 1e-4)
    epsilon = sigma * 0.12 + 1e-4
    if abs(alpha - 1.0) < 1e-6:
        span = math.log((sigma + epsilon) / epsilon)
        value = math.exp(rng.random() * span) * epsilon - epsilon
    else:
        exponent = 1.0 - alpha
        base = (sigma + epsilon) ** exponent - epsilon ** exponent
        value = (rng.random() * base + epsilon ** exponent) ** (1.0 / exponent) - epsilon
    return clamp(value, 0.0, sigma)


def _sample_background_position(
    rng: random.Random,
    projection: ProjectionParams,
    config: BackgroundDistribution,
) -> Tuple[float, float, float]:
    if config.max_r > config.min_r:
        u = rng.random()
        radius = math.sqrt(
            u * (config.max_r * config.max_r - config.min_r * config.min_r)
            + config.min_r * config.min_r
        )
        angle = rng.random() * math.tau
        x, y, depth = projection.project(radius, angle)
    else:
        x = rng.random() * projection.width
        y = rng.random() * projection.height
        depth = projection.distance
    jitter = config.jitter * projection.base_radius
    x += rng.uniform(-jitter, jitter)
    y += rng.uniform(-jitter * 0.6, jitter * 0.6)
    return x, y, depth


def generate_star_field(
    config: StarConfig,
    projection: ProjectionParams,
    rng: random.Random,
    ssaa: int,
) -> List[Star]:
    warm_color = hex_to_rgb(config.warm_color)
    hot_color = hex_to_rgb(config.hot_color)
    background_color = hex_to_rgb(config.background_color)

    stars: List[Star] = []

    for _ in range(config.bulge.count):
        angle = rng.random() * math.tau
        radius = _sample_bulge_radius(
            rng, config.bulge.sigma, config.bulge.falloff_alpha
        )
        x, y, depth = projection.project(radius, angle)
        scale = clamp(depth / projection.distance, 0.4, 2.2)
        size = rng.uniform(*config.bulge.size_px) * ssaa * clamp(scale, 0.7, 1.8)
        tightness = clamp(1.0 - radius / max(config.bulge.sigma, 1e-3), 0.0, 1.0)
        color_mix = clamp(tightness ** 0.85 + rng.random() * 0.2, 0.0, 1.0)
        color = mix_colors(warm_color, hot_color, color_mix)
        intensity = (1.15 + rng.random() * 1.5) * clamp(scale ** 0.6, 0.6, 1.9)
        stars.append(Star(x=x, y=y, radius=size, intensity=intensity, color=color))

    for _ in range(config.background.count):
        x, y, depth = _sample_background_position(rng, projection, config.background)
        scale = clamp(depth / projection.distance, 0.5, 1.6)
        size = rng.uniform(*config.background.size_px) * ssaa * clamp(scale, 0.6, 1.4)
        intensity = 0.35 + rng.random() * 0.65
        hue_mix = clamp(rng.random() * 0.35 + 0.2, 0.0, 1.0)
        color = mix_colors(background_color, warm_color, hue_mix)
        stars.append(Star(x=x, y=y, radius=size, intensity=intensity, color=color))

    return stars


def render_star_field(stars: List[Star], projection: ProjectionParams) -> FloatImage:
    image = FloatImage.new(projection.width, projection.height, 0.0)
    for star in stars:
        sigma = max(0.5, star.radius / 2.0)
        image.add_gaussian(star.x, star.y, sigma, star.intensity, star.color)
    return image


def downsample(image: FloatImage, factor: int) -> FloatImage:
    return image.downsample(factor)


__all__ = ["Star", "generate_star_field", "render_star_field", "downsample"]
