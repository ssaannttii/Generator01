"""Post-processing operations implemented in pure Python."""
from __future__ import annotations

import math
import random
from typing import Dict, Sequence, Tuple

from .image import FloatImage, gaussian_blur, gaussian_kernel
from .utils import clamp


def _bright_pass(image: FloatImage, threshold: float) -> FloatImage:
    width, height = image.width, image.height
    bright = FloatImage.new(width, height, 0.0)
    source_pixels = image.pixels
    bright_pixels = bright.pixels
    for y in range(height):
        src_row = source_pixels[y]
        dst_row = bright_pixels[y]
        for x in range(width):
            r, g, b = src_row[x]
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if luma <= threshold or luma <= 1e-5:
                continue
            scale = (luma - threshold) / luma
            dst_pixel = dst_row[x]
            dst_pixel[0] = r * scale
            dst_pixel[1] = g * scale
            dst_pixel[2] = b * scale
    return bright


def _select_downsample_factor(sigma: float, width: int, height: int) -> int:
    factor = 1
    while sigma / factor > 6.0 and min(width // (factor * 2), height // (factor * 2)) >= 8:
        factor *= 2
    return factor


def _get_downsampled(
    image: FloatImage, factor: int, cache: Dict[int, FloatImage]
) -> FloatImage:
    if factor <= 1:
        return image
    cached = cache.get(factor)
    if cached is not None:
        return cached
    parent = _get_downsampled(image, factor // 2, cache)
    downsampled = parent.downsample(2)
    cache[factor] = downsampled
    return downsampled


def _resample_nearest(image: FloatImage, width: int, height: int) -> FloatImage:
    result = FloatImage.new(width, height, 0.0)
    src_pixels = image.pixels
    dst_pixels = result.pixels
    src_width = max(1, image.width)
    src_height = max(1, image.height)
    for y in range(height):
        src_y = min(src_height - 1, (y * src_height) // height)
        src_row = src_pixels[src_y]
        dst_row = dst_pixels[y]
        for x in range(width):
            src_x = min(src_width - 1, (x * src_width) // width)
            src_pixel = src_row[src_x]
            dst_pixel = dst_row[x]
            dst_pixel[0] = src_pixel[0]
            dst_pixel[1] = src_pixel[1]
            dst_pixel[2] = src_pixel[2]
    return result


def _horizontal_gaussian(image: FloatImage, sigma: float) -> FloatImage:
    if sigma <= 0:
        return image.copy()
    kernel, radius = gaussian_kernel(sigma)
    width, height = image.width, image.height
    result = FloatImage.new(width, height, 0.0)
    src_pixels = image.pixels
    dst_pixels = result.pixels
    for y in range(height):
        src_row = src_pixels[y]
        dst_row = dst_pixels[y]
        for x in range(width):
            acc0 = acc1 = acc2 = 0.0
            start = x - radius
            kernel_index = 0
            if start < 0:
                kernel_index = -start
                start = 0
            end = x + radius + 1
            if end > width:
                end = width
            for xx in range(start, end):
                weight = kernel[kernel_index]
                pixel = src_row[xx]
                acc0 += pixel[0] * weight
                acc1 += pixel[1] * weight
                acc2 += pixel[2] * weight
                kernel_index += 1
            dst_pixel = dst_row[x]
            dst_pixel[0] = acc0
            dst_pixel[1] = acc1
            dst_pixel[2] = acc2
    return result


def apply_bloom(
    image: FloatImage,
    threshold: float,
    sigmas: Sequence[float],
    intensities: Sequence[float],
) -> Tuple[FloatImage, FloatImage]:
    bright = _bright_pass(image, threshold)
    result = image.copy()
    downsample_cache: Dict[int, FloatImage] = {1: bright}
    blurred_cache: Dict[Tuple[int, float], FloatImage] = {}
    target_width, target_height = image.width, image.height
    for sigma, intensity in zip(sigmas, intensities):
        if intensity <= 0.0 or sigma <= 0.0:
            continue
        factor = _select_downsample_factor(sigma, bright.width, bright.height)
        base = _get_downsampled(bright, factor, downsample_cache)
        adjusted_sigma = sigma / factor
        cache_key = (factor, round(adjusted_sigma, 6))
        blurred = blurred_cache.get(cache_key)
        if blurred is None:
            blurred_image = gaussian_blur(base, adjusted_sigma)
            if factor != 1:
                blurred = _resample_nearest(
                    blurred_image, target_width, target_height
                )
            else:
                blurred = blurred_image
            blurred_cache[cache_key] = blurred
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

    sigma = max(1.0, length_px / 6.0)
    downsample_cache: Dict[int, FloatImage] = {1: bright_pass}
    factor = _select_downsample_factor(sigma, bright_pass.width, bright_pass.height)
    base = _get_downsampled(bright_pass, factor, downsample_cache)
    streak_base = _horizontal_gaussian(base, sigma / factor)
    if factor != 1:
        streak = _resample_nearest(streak_base, image.width, image.height)
    else:
        streak = streak_base

    image.add_scaled_image(streak, intensity)
    return image


def apply_chromatic_aberration(
    image: FloatImage, *, pixels: float, center: Tuple[float, float] | None = None
) -> FloatImage:
    if abs(pixels) < 1e-6:
        return image.copy()

    width, height = image.width, image.height
    result = FloatImage.new(width, height, 0.0)
    if center is not None:
        cx, cy = center
    else:
        cx = (width - 1) / 2.0
        cy = (height - 1) / 2.0
    max_radius = math.hypot(max(cx, width - cx), max(cy, height - cy))
    max_radius = max(max_radius, 1.0)

    result_pixels = result.pixels
    source_pixels = image.pixels
    for y in range(height):
        dst_row = result_pixels[y]
        for x in range(width):
            dx = x - cx
            dy = y - cy
            radius = math.hypot(dx, dy)
            if radius <= 1e-6:
                pixel = source_pixels[y][x]
                dst_pixel = dst_row[x]
                dst_pixel[0] = pixel[0]
                dst_pixel[1] = pixel[1]
                dst_pixel[2] = pixel[2]
                continue
            shift = (radius / max_radius) * pixels
            nx = dx / radius
            ny = dy / radius
            red_sample = image.sample(x + nx * shift, y + ny * shift)
            green_sample = image.sample(x, y)
            blue_sample = image.sample(x - nx * shift, y - ny * shift)
            dst_pixel = dst_row[x]
            dst_pixel[0] = red_sample[0]
            dst_pixel[1] = green_sample[1]
            dst_pixel[2] = blue_sample[2]
    return result


def apply_vignette(image: FloatImage, strength: float) -> FloatImage:
    if strength <= 0:
        return image.copy()
    result = image.copy()
    cx = (image.width - 1) / 2.0
    cy = (image.height - 1) / 2.0
    max_radius = math.sqrt(cx * cx + cy * cy)
    result_pixels = result.pixels
    width, height = image.width, image.height
    for y in range(height):
        dst_row = result_pixels[y]
        for x in range(width):
            dx = x - cx
            dy = y - cy
            factor = 1.0 - strength * ((math.sqrt(dx * dx + dy * dy) / max_radius) ** 1.5)
            factor = max(0.0, min(1.0, factor))
            pixel = dst_row[x]
            pixel[0] *= factor
            pixel[1] *= factor
            pixel[2] *= factor
    return result


def add_grain(image: FloatImage, amount: float, rng: random.Random) -> FloatImage:
    if amount <= 0:
        return image.copy()
    result = image.copy()
    result_pixels = result.pixels
    for row in result_pixels:
        for pixel in row:
            noise = rng.gauss(0.0, amount)
            r = pixel[0] + noise
            g = pixel[1] + noise
            b = pixel[2] + noise
            pixel[0] = r if r > 0.0 else 0.0
            pixel[1] = g if g > 0.0 else 0.0
            pixel[2] = b if b > 0.0 else 0.0
    return result


def tone_map_aces(image: FloatImage, gamma: float = 2.2) -> FloatImage:
    result = image.copy()
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    inv_gamma = 1.0 / max(gamma, 1e-3)
    result_pixels = result.pixels
    for row in result_pixels:
        for pixel in row:
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
