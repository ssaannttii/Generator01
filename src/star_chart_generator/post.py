"""Post-processing operations implemented in pure Python."""
from __future__ import annotations

import math
import random
from typing import Sequence, Tuple

from .image import FloatImage, gaussian_blur
from .utils import clamp


def _bright_pass(image: FloatImage, threshold: float) -> FloatImage:
    bright = FloatImage.new(image.width, image.height, 0.0)
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = image.get_pixel(x, y)
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if luma <= threshold:
                continue
            scale = (luma - threshold) / max(luma, 1e-5)
            bright.pixels[y][x][0] = r * scale
            bright.pixels[y][x][1] = g * scale
            bright.pixels[y][x][2] = b * scale
    return bright


def apply_bloom(
    image: FloatImage,
    threshold: float,
    sigmas: Sequence[float],
    intensities: Sequence[float],
) -> Tuple[FloatImage, FloatImage]:
    bright = _bright_pass(image, threshold)
    result = image.copy()
    for sigma, intensity in zip(sigmas, intensities):
        if intensity <= 0.0 or sigma <= 0.0:
            continue
        blurred = gaussian_blur(bright, sigma)
        result.add_scaled_image(blurred, intensity)
    return result, bright


def apply_anamorphic_streak(
    image: FloatImage,
    bright_pass: FloatImage,
    *,
    length_px: float,
    intensity: float,
) -> FloatImage:
    if intensity <= 0.0 or length_px <= 0.0:
        return image

    radius = max(1, int(length_px))
    sigma = max(1.0, length_px / 6.0)
    kernel = [math.exp(-(i * i) / (2.0 * sigma * sigma)) for i in range(-radius, radius + 1)]
    norm = sum(kernel)
    kernel = [value / norm for value in kernel]

    streak = FloatImage.new(image.width, image.height, 0.0)
    for y in range(image.height):
        for x in range(image.width):
            acc = [0.0, 0.0, 0.0]
            for offset, weight in enumerate(kernel):
                xx = x + offset - radius
                if 0 <= xx < image.width:
                    pixel = bright_pass.pixels[y][xx]
                    acc[0] += pixel[0] * weight
                    acc[1] += pixel[1] * weight
                    acc[2] += pixel[2] * weight
            streak.pixels[y][x][0] = acc[0]
            streak.pixels[y][x][1] = acc[1]
            streak.pixels[y][x][2] = acc[2]

    image.add_scaled_image(streak, intensity)
    return image


def apply_chromatic_aberration(
    image: FloatImage, *, pixels: float, center: Tuple[float, float] | None = None
) -> FloatImage:
    if abs(pixels) < 1e-6:
        return image.copy()

    result = FloatImage.new(image.width, image.height, 0.0)
    if center is not None:
        cx, cy = center
    else:
        cx = (image.width - 1) / 2.0
        cy = (image.height - 1) / 2.0
    max_radius = math.hypot(max(cx, image.width - cx), max(cy, image.height - cy))
    max_radius = max(max_radius, 1.0)

    for y in range(image.height):
        for x in range(image.width):
            dx = x - cx
            dy = y - cy
            radius = math.hypot(dx, dy)
            if radius <= 1e-6:
                pixel = image.pixels[y][x]
                result.pixels[y][x][0] = pixel[0]
                result.pixels[y][x][1] = pixel[1]
                result.pixels[y][x][2] = pixel[2]
                continue
            shift = (radius / max_radius) * pixels
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


def tone_map_aces(image: FloatImage, gamma: float = 2.2) -> FloatImage:
    result = image.copy()
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    inv_gamma = 1.0 / max(gamma, 1e-3)
    for y in range(image.height):
        for x in range(image.width):
            pixel = result.pixels[y][x]
            for i in range(3):
                value = pixel[i]
                mapped = (value * (a * value + b)) / (value * (c * value + d) + e)
                mapped = clamp(mapped, 0.0, 1.0)
                pixel[i] = clamp(mapped ** inv_gamma, 0.0, 1.0)
    return result


__all__ = [
    "apply_bloom",
    "apply_anamorphic_streak",
    "apply_chromatic_aberration",
    "apply_vignette",
    "add_grain",
    "tone_map_aces",
]
