"""Post-processing operations implemented in pure Python."""
from __future__ import annotations

import math
import random
from typing import Tuple

from .image import FloatImage, gaussian_blur


def apply_bloom(image: FloatImage, threshold: float, intensity: float, radius: float) -> FloatImage:
    bright = FloatImage.new(image.width, image.height, 0.0)
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = image.get_pixel(x, y)
            bright.pixels[y][x][0] = max(r - threshold, 0.0)
            bright.pixels[y][x][1] = max(g - threshold, 0.0)
            bright.pixels[y][x][2] = max(b - threshold, 0.0)
    blurred = gaussian_blur(bright, max(1.0, radius / 3.0))
    result = image.copy()
    result.add_scaled_image(blurred, intensity)
    return result


def apply_chromatic_aberration(image: FloatImage, k: float) -> FloatImage:
    if abs(k) < 1e-6:
        return image.copy()
    result = FloatImage.new(image.width, image.height, 0.0)
    cx = (image.width - 1) / 2.0
    cy = (image.height - 1) / 2.0
    for y in range(image.height):
        for x in range(image.width):
            dx = x - cx
            dy = y - cy
            radius = math.sqrt(dx * dx + dy * dy) + 1e-6
            shift = k * (radius ** 2)
            nx = dx / radius
            ny = dy / radius
            red_sample = image.sample(x + nx * shift, y + ny * shift)
            green_sample = image.sample(x, y)
            blue_sample = image.sample(x - nx * shift, y - ny * shift)
            result.pixels[y][x][0] = red_sample[0]
            result.pixels[y][x][1] = green_sample[1]
            result.pixels[y][x][2] = blue_sample[2]
    return result


def apply_vignette(image: FloatImage, strength: float) -> FloatImage:
    if strength <= 0:
        return image.copy()
    result = image.copy()
    cx = (image.width - 1) / 2.0
    cy = (image.height - 1) / 2.0
    max_radius = math.sqrt(cx * cx + cy * cy)
    for y in range(image.height):
        for x in range(image.width):
            dx = x - cx
            dy = y - cy
            factor = 1.0 - strength * ((math.sqrt(dx * dx + dy * dy) / max_radius) ** 1.5)
            factor = max(0.0, min(1.0, factor))
            pixel = result.pixels[y][x]
            pixel[0] *= factor
            pixel[1] *= factor
            pixel[2] *= factor
    return result


def add_grain(image: FloatImage, amount: float, rng: random.Random) -> FloatImage:
    if amount <= 0:
        return image.copy()
    result = image.copy()
    for y in range(image.height):
        for x in range(image.width):
            noise = rng.gauss(0.0, amount)
            pixel = result.pixels[y][x]
            pixel[0] = max(0.0, pixel[0] + noise)
            pixel[1] = max(0.0, pixel[1] + noise)
            pixel[2] = max(0.0, pixel[2] + noise)
    return result


def tone_map_aces(image: FloatImage) -> FloatImage:
    result = image.copy()
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    for y in range(image.height):
        for x in range(image.width):
            pixel = result.pixels[y][x]
            for i in range(3):
                value = pixel[i]
                pixel[i] = max(0.0, min(1.0, (value * (a * value + b)) / (value * (c * value + d) + e)))
    return result


__all__ = [
    "apply_bloom",
    "apply_chromatic_aberration",
    "apply_vignette",
    "add_grain",
    "tone_map_aces",
]
