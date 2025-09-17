"""Utility helpers shared across the generator modules."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp ``value`` between ``lo`` and ``hi``."""

    return max(lo, min(hi, value))


def hex_to_rgb(color: str) -> Tuple[float, float, float]:
    """Convert a hex color string into an RGB tuple with floats in ``[0, 1]``."""

    color = color.strip()
    if color.startswith("#"):
        color = color[1:]
    if len(color) not in (3, 6):
        raise ValueError(f"Unsupported color format: {color!r}")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    return (r / 255.0, g / 255.0, b / 255.0)


def rgb_to_rgba(color: Sequence[float], alpha: float = 1.0) -> Tuple[int, int, int, int]:
    """Convert an ``RGB`` float tuple to 8-bit RGBA."""

    r, g, b = color
    a = clamp(alpha, 0.0, 1.0)
    return (
        int(clamp(r, 0.0, 1.0) * 255 + 0.5),
        int(clamp(g, 0.0, 1.0) * 255 + 0.5),
        int(clamp(b, 0.0, 1.0) * 255 + 0.5),
        int(a * 255 + 0.5),
    )


def mix_colors(color_a: Sequence[float], color_b: Sequence[float], t: float) -> Tuple[float, float, float]:
    """Linearly mix ``color_a`` and ``color_b``."""

    t = clamp(t, 0.0, 1.0)
    return tuple((1.0 - t) * a + t * b for a, b in zip(color_a, color_b))


def ensure_path(candidate: Optional[str], *, search_paths: Sequence[Path]) -> Optional[Path]:
    """Return the first existing path matching ``candidate`` in ``search_paths``."""

    if not candidate:
        return None
    path = Path(candidate)
    if path.is_file():
        return path
    for base in search_paths:
        probe = base / candidate
        if probe.is_file():
            return probe
        if not probe.suffix:
            ttf = probe.with_suffix(".ttf")
            if ttf.is_file():
                return ttf
    return None


__all__ = ["clamp", "hex_to_rgb", "rgb_to_rgba", "mix_colors", "ensure_path"]
