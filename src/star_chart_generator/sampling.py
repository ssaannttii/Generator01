"""Sampling utilities for procedural star placement."""
from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple


def sample_sersic(count: int, sigma: float, alpha: float, rng: random.Random) -> List[float]:
    """Sample radii following una aproximación de perfil de Sérsic."""
    radii: List[float] = []
    alpha = max(alpha, 1e-6)
    for _ in range(count):
        u = min(max(rng.random(), 1e-6), 1 - 1e-6)
        radius = sigma * (-math.log1p(-u)) ** (1.0 / alpha)
        radii.append(min(radius, 1.0))
    return radii


def sample_annulus(
    count: int,
    min_r: float,
    max_r: float,
    rng: random.Random,
    min_separation: float = 0.0,
) -> Tuple[List[float], List[float]]:
    """Sample polar coordinates dentro de un anillo con separación angular opcional."""
    radii: List[float] = []
    angles: List[float] = []
    min_r = max(0.0, min_r)
    max_r = max(min_r + 1e-6, max_r)
    step = 2 * math.pi / max(count, 1)
    for index in range(count):
        base_angle = index * step
        jitter = rng.uniform(0.0, step)
        angles.append(base_angle + jitter)
        radii.append(math.sqrt(rng.uniform(min_r * min_r, max_r * max_r)))
    if min_separation > 0.0 and count > 1:
        min_delta = min_separation / max(max_r, 1e-6)
        angles.sort()
        two_pi = 2 * math.pi
        for _ in range(2):
            for i in range(1, count):
                delta = angles[i] - angles[i - 1]
                if delta < min_delta:
                    angles[i] = angles[i - 1] + min_delta
            wrap_delta = (angles[0] + two_pi) - angles[-1]
            if wrap_delta < min_delta:
                angles[-1] = angles[0] + two_pi - min_delta
            angles = [angle % two_pi for angle in angles]
            angles.sort()
    return radii, angles


def sample_powerlaw_brightness(count: int, power: float, rng: random.Random) -> List[float]:
    power = max(power, 1e-6)
    values: List[float] = []
    for _ in range(count):
        u = min(max(rng.random(), 1e-6), 1 - 1e-6)
        values.append((1.0 - u) ** (1.0 / power))
    return values


__all__ = [
    "sample_sersic",
    "sample_annulus",
    "sample_powerlaw_brightness",
]
