"""Post-processing utilities for the star chart renderer (Pillow edition)."""
from __future__ import annotations

import math
import random
from typing import Tuple

from PIL import Image

from .config import PostProcessingSettings
from .imageops import FloatImage


def apply_postprocessing(image: FloatImage, settings: PostProcessingSettings, rng: random.Random) -> FloatImage:
    working = image.copy()
    bloom = _compute_bloom(working, settings)
    if bloom is not None:
        working.add(bloom)
    working = _apply_chromatic_aberration(working, settings.chromatic_aberration.strength)
    working = _apply_vignette(working, settings.vignette)
    working = _apply_grain(working, settings.grain.strength, rng)
    return working


def _compute_bloom(image: FloatImage, settings: PostProcessingSettings) -> FloatImage | None:
    if settings.bloom.intensity <= 0:
        return None
    bright = _bright_pass(image, settings.bloom.threshold)
    accumulation = FloatImage.blank(image.width, image.height)
    for radius in settings.bloom.radii:
        if radius <= 0:
            continue
        accumulation.add(bright.blur(radius))
    accumulation_scaled = accumulation.apply_point(lambda v: v * settings.bloom.intensity)
    return accumulation_scaled


def _bright_pass(image: FloatImage, threshold: float) -> FloatImage:
    result = FloatImage.blank(image.width, image.height)
    for idx in range(3):
        src = image.channels[idx].load()
        dst = result.channels[idx].load()
        for y in range(image.height):
            for x in range(image.width):
                value = src[x, y] - threshold
                dst[x, y] = value if value > 0.0 else 0.0
    return result


def _apply_chromatic_aberration(image: FloatImage, strength: float) -> FloatImage:
    if strength <= 0:
        return image
    width, height = image.width, image.height
    cx = (width - 1) * 0.5
    cy = (height - 1) * 0.5
    max_radius = math.sqrt(cx * cx + cy * cy)
    source = [channel.load() for channel in image.channels]
    result = image.clone_blank()
    dest = [channel.load() for channel in result.channels]
    offsets = [1.0, 0.35, -1.0]
    for y in range(height):
        for x in range(width):
            dx = x - cx
            dy = y - cy
            radius = math.sqrt(dx * dx + dy * dy)
            if radius < 1e-6:
                for idx in range(3):
                    dest[idx][x, y] = source[idx][x, y]
                continue
            unit_x = dx / radius
            unit_y = dy / radius
            shift_base = strength * (radius / max_radius) ** 2 * min(width, height)
            for idx, offset in enumerate(offsets):
                sample_x = x + unit_x * shift_base * offset
                sample_y = y + unit_y * shift_base * offset
                dest[idx][x, y] = _bilinear_sample(source[idx], width, height, sample_x, sample_y)
    return result


def _bilinear_sample(pixels, width: int, height: int, x: float, y: float) -> float:
    x = min(max(x, 0.0), width - 1.0)
    y = min(max(y, 0.0), height - 1.0)
    x0 = int(math.floor(x))
    x1 = min(x0 + 1, width - 1)
    y0 = int(math.floor(y))
    y1 = min(y0 + 1, height - 1)
    wx = x - x0
    wy = y - y0
    top = pixels[x0, y0] * (1.0 - wx) + pixels[x1, y0] * wx
    bottom = pixels[x0, y1] * (1.0 - wx) + pixels[x1, y1] * wx
    return top * (1.0 - wy) + bottom * wy


def _apply_vignette(image: FloatImage, strength: float) -> FloatImage:
    if strength <= 0:
        return image
    width, height = image.width, image.height
    cx = (width - 1) * 0.5
    cy = (height - 1) * 0.5
    max_radius = math.sqrt(cx * cx + cy * cy)
    result = image.copy()
    for idx in range(3):
        src = image.channels[idx].load()
        dst = result.channels[idx].load()
        for y in range(height):
            for x in range(width):
                dx = x - cx
                dy = y - cy
                radius = math.sqrt(dx * dx + dy * dy) / max_radius
                factor = max(0.2, 1.0 - strength * (radius ** 1.5))
                dst[x, y] = src[x, y] * factor
    return result


def _apply_grain(image: FloatImage, strength: float, rng: random.Random) -> FloatImage:
    if strength <= 0:
        return image
    result = image.copy()
    for idx in range(3):
        src = image.channels[idx].load()
        dst = result.channels[idx].load()
        for y in range(image.height):
            for x in range(image.width):
                dst[x, y] = max(0.0, src[x, y] + rng.gauss(0.0, strength))
    return result


def tonemap_aces(image: FloatImage) -> Image.Image:
    channels_8bit = []
    for channel in image.channels:
        tonemapped = Image.new("F", (image.width, image.height))
        src = channel.load()
        dst = tonemapped.load()
        for y in range(image.height):
            for x in range(image.width):
                value = src[x, y]
                mapped = _aces_curve(value)
                dst[x, y] = 0.0 if mapped < 0.0 else (1.0 if mapped > 1.0 else mapped)
        channels_8bit.append(tonemapped.point(lambda v: int(max(0, min(255, round(v * 255.0))))))
    return Image.merge("RGB", tuple(channels_8bit))


def _aces_curve(value: float) -> float:
    a = 2.51
    b = 0.03
    c = 2.43
    d = 0.59
    e = 0.14
    numerator = value * (a * value + b)
    denominator = value * (c * value + d) + e
    if denominator == 0:
        return 0.0
    return numerator / denominator


__all__ = ["apply_postprocessing", "tonemap_aces"]
