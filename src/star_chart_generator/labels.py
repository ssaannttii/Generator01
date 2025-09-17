"""Curved text layout using a built-in bitmap font."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import math

from .config import TextConfig
from .image import FloatImage
from .utils import hex_to_rgb

Glyph = List[str]

FONT_DATA: Dict[str, Glyph] = {
    "A": ["  #  ", " # # ", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"],
    "D": ["###  ", "#  # ", "#   #", "#   #", "#   #", "#  # ", "###  "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": [" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "J": ["  ###", "   #", "   #", "   #", "#  #", "#  #", " ## "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", " # # ", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "# #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": [" ### ", "#   #", "    #", "  ## ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": [" ### ", "#   #", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "   # ", "  #  ", "  #  ", "  #  "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "#   #", " ### "],
    "-": ["     ", "     ", "     ", " ### ", "     ", "     ", "     "],
    ":": ["     ", "  #  ", "     ", "     ", "     ", "  #  ", "     "],
    ".": ["     ", "     ", "     ", "     ", "     ", "  ## ", "  ## "],
    " ": ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
}

GLYPH_WIDTH = 5
GLYPH_HEIGHT = 7


@dataclass
class LabelSpec:
    ring_index: int
    text: str
    center: Tuple[float, float]
    radius_x: float
    radius_y: float
    initial_angle: float
    tracking: float
    scale: float


@dataclass
class LabelPlacement:
    spec: LabelSpec
    theta: float
    arc_angle: float
    advances: List[float]


def _glyph(char: str) -> Glyph:
    return FONT_DATA.get(char.upper(), FONT_DATA[" "])


def _glyph_advance(char: str) -> float:
    glyph = _glyph(char)
    width = max(len(row) for row in glyph)
    return float(width + 1)


def _text_advances(text: str, tracking: float) -> List[float]:
    advances: List[float] = []
    for index, char in enumerate(text):
        advance = _glyph_advance(char)
        if index < len(text) - 1:
            advance += tracking / 6.0
        advances.append(max(0.4, advance))
    return advances


def _wrap(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def layout_labels(
    specs: Sequence[LabelSpec],
    *,
    padding: float = 0.06,
    iterations: int = 140,
) -> List[LabelPlacement]:
    placements: List[LabelPlacement] = []
    for spec in specs:
        effective_radius = max((spec.radius_x + spec.radius_y) * 0.5, 1.0)
        advances = _text_advances(spec.text, spec.tracking)
        arc_length = sum(advances) * spec.scale
        arc_angle = arc_length / effective_radius
        placements.append(
            LabelPlacement(
                spec=spec,
                theta=spec.initial_angle,
                arc_angle=arc_angle,
                advances=advances,
            )
        )

    by_ring: Dict[int, List[LabelPlacement]] = {}
    for placement in placements:
        by_ring.setdefault(placement.spec.ring_index, []).append(placement)

    for ring_placements in by_ring.values():
        if len(ring_placements) <= 1:
            continue
        for _ in range(iterations):
            moved = False
            for i in range(len(ring_placements)):
                for j in range(i + 1, len(ring_placements)):
                    a = ring_placements[i]
                    b = ring_placements[j]
                    diff = _wrap(b.theta - a.theta)
                    min_sep = (a.arc_angle + b.arc_angle) * 0.5 + padding
                    if abs(diff) < min_sep:
                        direction = 1.0 if diff >= 0 else -1.0
                        shift = (min_sep - abs(diff)) * 0.5
                        a.theta -= direction * shift
                        b.theta += direction * shift
                        moved = True
            if not moved:
                break
        for placement in ring_placements:
            placement.theta = _wrap(placement.theta)

    ordered: List[LabelPlacement] = []
    for spec in specs:
        for placement in placements:
            if placement.spec is spec:
                ordered.append(placement)
                break
    return ordered


def _draw_glyph(image: FloatImage, glyph: Glyph, center: Tuple[float, float], scale: float, rotation: float, color: Tuple[float, float, float], intensity: float) -> None:
    cx, cy = center
    angle = math.radians(rotation)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    for y, row in enumerate(glyph):
        for x, ch in enumerate(row):
            if ch != "#":
                continue
            px = (x - GLYPH_WIDTH / 2.0) * scale
            py = (y - GLYPH_HEIGHT / 2.0) * scale
            rx = px * cos_a - py * sin_a
            ry = px * sin_a + py * cos_a
            image.add_disc(cx + rx, cy + ry, max(0.5, scale * 0.45), color, intensity)


def draw_label_layers(
    size: Tuple[int, int],
    placements: Sequence[LabelPlacement],
    text_config: TextConfig,
) -> Tuple[FloatImage, FloatImage]:
    width, height = size
    core = FloatImage.new(width, height, 0.0)
    glow = FloatImage.new(width, height, 0.0)
    base_color = hex_to_rgb(text_config.color)
    for placement in placements:
        scale = placement.spec.scale
        effective_radius = max((placement.spec.radius_x + placement.spec.radius_y) * 0.5, 1.0)
        theta = placement.theta - placement.arc_angle / 2.0
        for advance, char in zip(placement.advances, placement.spec.text):
            theta += (advance * scale) / (2.0 * effective_radius)
            x = placement.spec.center[0] + placement.spec.radius_x * math.cos(theta)
            y = placement.spec.center[1] + placement.spec.radius_y * math.sin(theta)
            rotation = math.degrees(theta) - 90.0
            glyph = _glyph(char)
            _draw_glyph(core, glyph, (x, y), scale, rotation, base_color, 1.0)
            _draw_glyph(glow, glyph, (x, y), scale * 1.6, rotation, base_color, 0.2)
            theta += (advance * scale) / (2.0 * effective_radius)

    return core, glow


__all__ = ["LabelSpec", "LabelPlacement", "layout_labels", "draw_label_layers"]
